"""PLAN-v5 F5: memory in Obsidian with ONE writer. The vault is a copy of the journal, written as things happen,
never read back. Real bridge + gateway + app API + fake extension; the vault is a temporary folder."""

from __future__ import annotations

import asyncio
import builtins
import io
import json
import os
import re
import shutil
from pathlib import Path

import pytest

from test_appapi import AUTH, App, run
from test_gateway import ask, b64, gw
from webllm_agent import vault


def on(app, tmp_path) -> Path:
    folder = tmp_path / "Mi unidad" / "Obsidian"
    folder.mkdir(parents=True)
    vault.configure(app.cfg.paths, str(folder))
    assert vault.flush(10)
    return folder / "webllm"


def notes(base: Path) -> list[Path]:
    assert vault.flush(10)
    return sorted(p for p in base.rglob("*.md") if p.name != "Índice.md")


def sections(note: str) -> list[tuple[str, str]]:
    """(heading, body) of each "## ..." section of a note."""
    parts = re.split(r"^## (.+)$", note, flags=re.M)
    return [(parts[i].strip(), parts[i + 1].strip()) for i in range(1, len(parts), 2)]


def answers_in(note: str, label: str) -> list[str]:
    """The text of each answer by ``label``, without webllm's footer."""
    return [body.split("\n\n<small>")[0].strip() for head, body in sections(note) if head.split(" · ")[0] == label]


def journal_answers(app, run_id: str) -> list[str]:
    """The same answers, straight from the journal's response files (checked against their sha256)."""
    from webllm_agent.broadcaster import verify_run
    run_dir = app.cfg.paths.runs_dir / run_id
    assert verify_run(run_dir).ok
    lines = [json.loads(x) for x in (run_dir / "journal.jsonl").read_text("utf-8").splitlines() if x.strip()]
    return [(run_dir / x["response_file"]).read_text("utf-8").strip() for x in lines if x.get("response_file")]


def test_the_folder_must_exist_and_be_writable(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            with pytest.raises(ValueError, match="ruta completa"):
                vault.configure(app.cfg.paths, "Obsidian")
            with pytest.raises(ValueError, match="no existe"):
                vault.configure(app.cfg.paths, str(tmp_path / "nada"))
            assert vault.settings(app.cfg.paths)["enabled"] is False
            # through the app: the same Spanish reason, and nothing turned on
            async with app.http.post(app.url("/api/memoria"), json={"dir": str(tmp_path / "nada")}, headers=AUTH) as r:
                assert r.status == 400 and "no existe" in (await r.json())["error"]
            folder = tmp_path / "Mi unidad" / "Obsidian"
            folder.mkdir(parents=True)
            async with app.http.post(app.url("/api/memoria"), json={"dir": f'"{folder}"'}, headers=AUTH) as r:
                m = await r.json()
                assert r.status == 200 and m["enabled"] and m["dir"] == str(folder) and m["conversations"] == 0
            assert (folder / "webllm").is_dir() and [p.name for p in folder.iterdir()] == ["webllm"]
            assert vault.flush(10)  # the write probe left nothing; an index (still empty) says it works
            assert [p.name for p in (folder / "webllm").iterdir()] == ["Índice.md"]
            async with app.http.post(app.url("/api/memoria"), json={"enabled": False}, headers=AUTH) as r:
                m = await r.json()
                assert not m["enabled"] and m["dir"] == str(folder)  # off keeps the folder for next time
            async with app.http.get(app.url("/api/memoria"), headers={}) as r:
                assert r.status == 401
    run(go())


def test_a_conversation_is_one_note_written_as_it_happens_and_identical_to_the_journal(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, behaviour={"qwen": "silent"}) as app:
            base = on(app, tmp_path)
            # 1. while Qwen is still answering, the question is already in the note
            asking = asyncio.create_task(gw(app, ask("qwen", "¿Qué es la inflación?", chat_id="c-1")))
            for _ in range(50):
                await asyncio.sleep(0.1)
                if app.bridge.jobs.get("qwen"):
                    break
            (note,) = notes(base)
            assert note.parent.name == vault.NO_PROJECT and note.name.endswith(" ¿Qué es la inflación.md")
            mid = note.read_text("utf-8")
            assert "## Tú" in mid and "¿Qué es la inflación?" in mid and "esperando la respuesta" in mid
            app.bridge.cancel("qwen")  # Iván stops it: the note says so, in his words
            _, _, h1 = await asyncio.wait_for(asking, 10)
            assert "Lo has parado tú" in notes(base)[0].read_text("utf-8")
            # 2. the next questions of the same conversation go to the same note, verbatim
            texts = ["La **inflación** es…\n\n| a | b |\n|---|---|\n| 1 | 2 |",
                     "Con `código`:\n\n```python\nprint('ñ')\n```\n\n- lista\n  - anidada",
                     "Emoji 🚀, $x^2$, [[no es un enlace]] y <b>html</b>."]
            runs = [h1["x-webllm-run"]]
            for n, text in enumerate(texts):
                app.ext.behaviour["qwen"] = {"ok": True, "text": text, "via": "copy-button"}
                _, _, h = await gw(app, ask("qwen", f"pregunta {n}", chat_id="c-1"))
                runs.append(h["x-webllm-run"])
            (same,) = notes(base)
            assert same == note
            text = note.read_text("utf-8")
            assert [a for r in runs for a in journal_answers(app, r)] == texts
            assert answers_in(text, "Qwen") == ["*(Sin respuesta. Lo has parado tú.)*", *texts]
            assert text.count("## Tú") == 4 and "esperando la respuesta" not in text
            index = (base / "Índice.md").read_text("utf-8")
            assert f"](<{vault.NO_PROJECT}/{note.name}>)" in index and "4 preguntas" in index
    run(go())


def test_ten_conversations_in_a_row_all_in_the_vault_identical_to_the_journal(tmp_path, mock_server):
    """F5's exit: 10 conversations, the 10 in the vault, identical to the journal."""
    def page(job):
        return {"ok": True, "text": f"Respuesta a: {job['prompt'][-40:]}\n\n1. uno\n2. dos", "via": "copy-button"}

    async def go():
        async with App(tmp_path, mock_server.base_url, behaviour={"qwen": page}) as app:
            base = on(app, tmp_path)
            runs = {}
            for n in range(10):
                model = "qwen" if n % 2 else "zai"
                _, _, h = await gw(app, ask(model, f"Conversación número {n}", chat_id=f"chat-{n}", title=f"Tema {n}"))
                runs[f"Tema {n}"] = (h["x-webllm-run"], "Qwen" if n % 2 else "z.ai")
            found = notes(base)
            assert len(found) == 10
            for note in found:
                text = note.read_text("utf-8")
                title = re.search(r"^# (.+)$", text, flags=re.M).group(1)
                run_id, label = runs[title]
                assert answers_in(text, label) == journal_answers(app, run_id) and run_id in text
            index = (base / "Índice.md").read_text("utf-8")
            assert all(f"[Tema {n}]" in index for n in range(10))
    run(go())


def test_the_project_is_the_open_webui_folder_and_strange_titles_are_safe(tmp_path, mock_server):
    titles = ["CON", 'a/b:c*?"<>|#^[]%', "Plan 🚀 de marketing", "   ...puntos...   ", "x" * 300, "数据分析：第一步",
              "New Chat", "", "nul.txt", "Tema", "tema"]

    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            base = on(app, tmp_path)
            for n, t in enumerate(titles):
                status, _, _ = await gw(app, ask("qwen", t or "hola", chat_id=f"c-{n}", title=t,
                                                 project="Clientes/2026: <nuevos>"))
                assert status == 200
            found = notes(base)
            assert len(found) == len(titles) and {p.parent.name for p in found} == {"Clientes 2026 nuevos"}
            names = [p.name for p in found]
            assert not any(re.search(r'[\\/:*?"<>|#^\[\]%]', n) for n in names)
            assert any("🚀" in n for n in names) and any("数据分析" in n for n in names)
            assert all(len(n) <= 100 for n in names)
            stems = [n[len("AAAA-MM-DD "):-3] for n in names]
            assert not any(s.lower().split(".")[0] in ("con", "nul", "") for s in stems)
            # "New Chat" (Open WebUI's placeholder) is not a title: the question names the note
            assert any(s == "New Chat" for s in stems)  # its question was the text "New Chat" itself
            assert len({n.lower() for n in names}) == len(names)  # "Tema" and "tema" never share a file (Windows)
            index = (base / "Índice.md").read_text("utf-8")
            for p in found:  # every link in the index points at a note that exists
                assert f"(<Clientes 2026 nuevos/{p.name}>)" in index
    run(go())


def test_the_vault_is_never_read(tmp_path, mock_server, monkeypatch):
    """Not one read: no file under the vault opened for reading, no listing of it (the writer runs in its own
    thread, so the watch is on the functions themselves)."""
    reads: list[str] = []
    real_open, real_io_open = builtins.open, io.open
    real_listdir, real_scandir, real_walk = os.listdir, os.scandir, os.walk
    root = str(tmp_path / "Mi unidad")

    def watch(path, mode="r", *a, **k):
        if str(path).startswith(root) and not any(c in mode for c in "wax"):
            reads.append(f"open {path} {mode}")
        return real_open(path, mode, *a, **k)

    def watch_list(fn):
        def inner(path=".", *a, **k):
            if str(path).startswith(root):
                reads.append(f"{fn.__name__} {path}")
            return fn(path, *a, **k)
        return inner

    def made(job):
        return {"ok": True, "text": "Hecha.", "via": "copy-button", "downloads": [{"name": "x.html", "b64": b64(b"<p>")}]}

    async def go():
        async with App(tmp_path, mock_server.base_url, behaviour={"qwen": made}) as app:
            on(app, tmp_path)
            monkeypatch.setattr(builtins, "open", watch)
            monkeypatch.setattr(io, "open", watch)
            monkeypatch.setattr(os, "listdir", watch_list(real_listdir))
            monkeypatch.setattr(os, "scandir", watch_list(real_scandir))
            monkeypatch.setattr(os, "walk", watch_list(real_walk))
            for n in range(3):
                await gw(app, ask("qwen", f"pregunta {n}", chat_id="c-x", files=[
                    {"name": "a.txt", "mime": "text/plain", "data": b64(b"hola")}]))
                await gw(app, ask("zai", f"otra {n}", chat_id=f"c-{n}", title="Título"))
            await app.ask("¿Qué es el IPC?", ["zai", "qwen"])
            vault.write_committee(app.cfg.paths, "Tema", "# Doc\n")
            assert vault.flush(10)
            vault.configure(app.cfg.paths, str(tmp_path / "Mi unidad" / "Obsidian"), enabled=False)
            (tmp_path / "Mi unidad" / "Otra").mkdir()
            vault.configure(app.cfg.paths, str(tmp_path / "Mi unidad" / "Otra"))  # a new vault gets everything
            assert vault.flush(10)
            for name, fn in (("open", real_open), ("io_open", real_io_open)):
                monkeypatch.setattr(builtins if name == "open" else io, "open", fn)
            monkeypatch.setattr(os, "listdir", real_listdir)
            monkeypatch.setattr(os, "scandir", real_scandir)
            monkeypatch.setattr(os, "walk", real_walk)
            written = sorted(p.relative_to(tmp_path / "Mi unidad" / "Otra") for p in (tmp_path / "Mi unidad" / "Otra").rglob("*.*"))
            assert len([p for p in written if p.suffix == ".md"]) == 1 + 4 + 1  # index + conversations; the doc stayed
            assert len([p for p in written if p.name == "a.txt"]) == 3 and len([p for p in written if p.name == "x.html"]) == 4
    run(go())
    assert reads == []


def test_off_writes_nothing_and_a_broken_vault_never_breaks_a_question(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            status, _, _ = await gw(app, ask("qwen", "hola", chat_id="c-1"))
            assert status == 200 and not (tmp_path / "Mi unidad").exists()  # off: nothing anywhere
            base = on(app, tmp_path)
            shutil.rmtree(base.parent)  # Drive closed: the vault folder is gone
            status, lines, _ = await gw(app, ask("qwen", "sigue funcionando", chat_id="c-1"))
            assert status == 200 and "answer from qwen" in json.dumps(lines)
            assert vault.flush(10)
            assert not base.parent.exists()  # never recreated where Iván's vault used to be
            async with app.http.get(app.url("/api/memoria"), headers=AUTH) as r:
                m = await r.json()
            assert m["enabled"] and "no está" in m["error"] and "Drive" in m["error"]  # the app says why
            base.parent.mkdir()  # Drive back: the next answer writes again and the failure is gone
            await gw(app, ask("qwen", "otra vez", chat_id="c-1"))
            (note,) = notes(base)
            assert note.read_text("utf-8").count("## Tú") == 2  # (the first question was asked while it was off)
            assert vault.settings(app.cfg.paths)["error"] is None
    run(go())


def test_a_slow_drive_never_holds_up_an_answer(tmp_path, mock_server, monkeypatch):
    """The writer is its own thread: an answer comes back while the vault takes 3 s per file."""
    import time as _time
    real = vault._atomic_write

    def slow(path, content):
        if "Mi unidad" in str(path):
            _time.sleep(3)
        real(path, content)

    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            base = on(app, tmp_path)
            monkeypatch.setattr(vault, "_atomic_write", slow)
            t0 = _time.monotonic()
            status, _, _ = await gw(app, ask("zai", "rápido", chat_id="c-1"))
            assert status == 200 and _time.monotonic() - t0 < 2.5
            assert vault.flush(30) and len(notes(base)) == 1
    run(go())


def test_what_a_chat_made_and_ivans_files_are_copied_next_to_the_note(tmp_path, mock_server):
    made = b"<html>web</html>"

    def page(job):
        return {"ok": True, "text": "Hecha.", "via": "copy-button",
                "downloads": [{"name": "web.html", "b64": b64(made)}, {"name": "web.html", "b64": b64(b"otra")},
                              {"name": "enlace.zip", "url": "https://chat.qwen.ai/f/1.zip"}]}

    async def go():
        async with App(tmp_path, mock_server.base_url, behaviour={"qwen": page}) as app:
            base = on(app, tmp_path)
            _, _, h = await gw(app, ask("qwen", "hazme una web", chat_id="c-9",
                                        files=[{"name": "plano.pdf", "mime": "application/pdf", "data": b64(b"%PDF-1")}]))
            run_id = h["x-webllm-run"]
            note = notes(base)[0].read_text("utf-8")
            adj = base / "Adjuntos" / run_id
            assert (adj / "web.html").read_bytes() == made and (adj / "web-2.html").read_bytes() == b"otra"
            assert (adj / "plano.pdf").read_bytes() == b"%PDF-1"
            assert f"[web.html](<../Adjuntos/{run_id}/web.html>)" in note
            assert f"[plano.pdf](<../Adjuntos/{run_id}/plano.pdf>)" in note
            assert "[enlace.zip](https://chat.qwen.ai/f/1.zip)" in note
            # a file changed after it was recorded is not copied: the vault only gets what the journal vouches for
            lines = [json.loads(x) for x in (app.cfg.paths.runs_dir / run_id / "journal.jsonl").read_text("utf-8").splitlines()]
            (made_here,) = [d for x in lines for d in x.get("downloads", []) if d.get("size") == len(made)]
            Path(made_here["path"]).write_bytes(b"cambiado")
            shutil.rmtree(adj)
            index = json.loads((app.cfg.paths.state_dir / "vault_index.json").read_text("utf-8"))
            index["copied"] = {}
            (app.cfg.paths.state_dir / "vault_index.json").write_text(json.dumps(index), "utf-8")
            await gw(app, ask("qwen", "y otra", chat_id="c-9"))
            notes(base)
            # the other "web.html" of that answer (still intact) takes the name; the changed one is not there
            assert (adj / "web.html").read_bytes() == b"otra" and (adj / "plano.pdf").exists()
            assert not any(p.read_bytes() == b"cambiado" for p in base.rglob("*") if p.is_file())
    run(go())


def test_the_apps_own_questions_and_the_committee_folder(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            base = on(app, tmp_path)
            status, events = await app.ask("¿Qué es el IPC?", ["zai", "qwen"])
            assert status == 200
            (note,) = notes(base)
            assert note.parent.name == vault.APP_PROJECT
            text = note.read_text("utf-8")
            run_id = next(e["run_id"] for e in events if e.get("type") == "flow_start")
            assert sorted([*answers_in(text, "z.ai"), *answers_in(text, "Qwen")]) == sorted(journal_answers(app, run_id))
            async with app.http.get(app.url("/api/memoria"), headers=AUTH) as r:
                m = await r.json()
            assert m["conversations"] == 1 and m["error"] is None and re.match(r"\d\d/\d\d/\d{4} a las \d\d:\d\d", m["last"])
            doc = vault.write_committee(app.cfg.paths, "¿Abrimos tienda online?", "# Documento de fusión\n")
            again = vault.write_committee(app.cfg.paths, "¿Abrimos tienda online?", "# Otro\n")
            assert vault.flush(10)
            assert doc.parent == base / "Comités" and doc.read_text("utf-8") == "# Documento de fusión\n"
            assert again.name.endswith("(2).md") and again.read_text("utf-8") == "# Otro\n"
    run(go())
