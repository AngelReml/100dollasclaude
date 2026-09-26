"""Memory in Obsidian with ONE writer (PLAN-v5 D5, F5): webllm's journal is the truth; the vault is a copy,
written one way, as things happen, and NEVER read back: no note is opened and no folder is listed. The only
look is whether the vault folder itself is still there, so webllm never recreates it where Iván moved it from.

    data/state/vault.json         where the vault is and whether it is on (this PC's setting, not in git)
    data/state/vault_status.json  the last write and its error, if any (only the writer writes it)
    data/state/vault_index.json   what webllm wrote and where: conversation -> note, its runs, its title

Everything goes under <vault>/webllm/ so it never touches Iván's own notes:

    <vault>/webllm/<Proyecto>/<AAAA-MM-DD> <título>.md   one note per conversation (Open WebUI chat, or one
                                                         question/chain from webllm's app)
    <vault>/webllm/Comités/                              the Committee's documents (F7)
    <vault>/webllm/Adjuntos/<run>/                       Iván's files and what a chat produced
    <vault>/webllm/Índice.md                             every conversation, by project

A note is rebuilt whole from the journal each time and replaced in one go (temp file + rename), so Drive
never syncs half a file and the note always matches the journal. All writing happens in one background
thread: a slow or unplugged Drive can never hold up a question, and since every note is rebuilt from the
journal at the moment it is written, the last write always has everything.
Links are relative Markdown links, so they work wherever the vault's root is, and outside Obsidian too.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import journal
from .problems import DEFAULT, PROBLEMS

if TYPE_CHECKING:
    from .config import Paths

SETTINGS = "vault.json"
STATUS = "vault_status.json"
INDEX = "vault_index.json"
ROOT = "webllm"
NO_PROJECT = "Sin proyecto"
APP_PROJECT = "Desde la app de webllm"
MAX_ATTACHMENT = 25 * 1024 * 1024
PLACEHOLDER_TITLES = {"new chat", "nuevo chat", "nueva conversación", "nueva conversacion", "chat", "untitled"}
_INDEX_LOCK = threading.Lock()
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


# ------------------------------------------------------------------ settings (this PC's, in data/state)

def settings(paths: "Paths") -> dict[str, Any]:
    data = _read_json(paths.state_dir / SETTINGS)
    folder = str(data.get("dir") or "")
    status = _read_json(paths.state_dir / STATUS)
    same = status.get("dir") == folder  # a failure in a folder Iván no longer uses is not news
    return {"dir": folder, "enabled": bool(data.get("enabled")) and bool(folder),
            "last": status.get("last") if same else None, "error": status.get("error") if same else None}


def configure(paths: "Paths", folder: str, enabled: bool = True) -> dict[str, Any]:
    """Point webllm at the vault. The folder must exist (Obsidian made it, inside Google Drive); webllm only
    creates its own webllm/ inside it. A new folder gets everything webllm already wrote elsewhere, so its
    index has no broken links. Raises ValueError with a Spanish message."""
    folder = folder.strip().strip('"').strip()
    old = settings(paths)
    if enabled:
        p = Path(folder)
        if not folder or not p.is_absolute():
            raise ValueError("Escribe la ruta completa de la carpeta de tu vault (por ejemplo G:\\Mi unidad\\Obsidian).")
        if not p.is_dir():
            raise ValueError("Esa carpeta no existe. Créala en Obsidian (o en Drive) y vuelve a probar.")
        try:
            (p / ROOT).mkdir(exist_ok=True)
            probe = p / ROOT / f".webllm-escritura-{os.getpid()}"
            probe.write_text("ok", encoding="utf-8")  # written and removed: nothing of Iván's is read
            probe.unlink()
        except OSError as exc:
            raise ValueError(f"No puedo escribir en esa carpeta ({exc.strerror or exc}).") from None
        folder = str(p)
    else:
        folder = folder or old["dir"]
    _write_json(paths.state_dir / SETTINGS, {"dir": folder, "enabled": enabled})
    if enabled and folder != old["dir"]:
        _WORKER.submit(("all", paths, None, None, None, None))
    return settings(paths)


# ------------------------------------------------------------------ names

def safe_name(title: str, limit: int = 80) -> str:
    """A file name any system and Obsidian accept: no \\ / : * ? " < > | # ^ [ ] % or control characters,
    no trailing dots/spaces, not a Windows reserved name, not empty. Letters of any language and emoji stay."""
    s = re.sub(r"[\x00-\x1f\x7f\\/:*?\"<>|#^\[\]%]+", " ", str(title or ""))
    s = re.sub(r"\s+", " ", s).strip(" .")[:limit].strip(" .")
    if not s or s.lower() in _WINDOWS_RESERVED or s.split(".")[0].lower() in _WINDOWS_RESERVED:
        s = f"Conversación {s}".strip()
    return s or "Conversación"


def _link(text: str, target: str) -> str:
    """A relative Markdown link (angle brackets: spaces and accents need no escaping)."""
    return f"[{text.replace('[', '(').replace(']', ')')}](<{target}>)"


# ------------------------------------------------------------------ files (webllm's own state, never the vault)

def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(data, indent=1, ensure_ascii=False))


def _put(base: Path, rel: str, content: str | bytes) -> None:
    """Write <vault>/webllm/<rel>. Folders are made one level at a time from webllm/ down, never above: if the
    vault goes away mid-way this fails instead of recreating it where it was."""
    folder = base
    folder.mkdir(exist_ok=True)
    for part in Path(rel).parent.parts:
        folder = folder / part
        folder.mkdir(exist_ok=True)
    _atomic_write(base / rel, content)


def _atomic_write(path: Path, content: str | bytes) -> None:
    """Replace the file in one go: Drive and Obsidian never see half a note."""
    fd, tmp = tempfile.mkstemp(prefix=".webllm-", suffix=".tmp", dir=path.parent)
    try:
        if isinstance(content, bytes):
            with os.fdopen(fd, "wb") as fh:
                fh.write(content)
        else:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ------------------------------------------------------------------ a run, read from the journal

def _run(run_dir: Path) -> dict[str, Any] | None:
    try:
        flow = json.loads((run_dir / "flow.json").read_text(encoding="utf-8"))
        raw = (run_dir / journal.JOURNAL_NAME).read_text(encoding="utf-8") if (run_dir / journal.JOURNAL_NAME).exists() else ""
    except (OSError, ValueError):
        return None
    lines = []
    for x in raw.split("\n"):
        try:
            lines.append(json.loads(x))
        except ValueError:
            break  # an empty end, or the line being written right now: the next write will have it
    lines = [x for x in lines if isinstance(x, dict)]
    inputs = flow.get("inputs") or {}
    steps = {s.get("id"): s.get("title") or s.get("id") for s in flow.get("steps") or []}
    gw = next((x for x in lines if x.get("kind") == "gateway"), {})
    answers = []
    for x in lines:
        if x.get("kind") != "flow":
            continue
        text = ""
        if x.get("response_file"):
            try:
                text = (run_dir / x["response_file"]).read_text(encoding="utf-8")
            except OSError:
                text = ""
        answers.append({"provider": x.get("provider"), "model": x.get("model"), "status": x.get("status"),
                        "code": x.get("code"), "text": text, "seconds": x.get("latency_s"),
                        "step": steps.get(x.get("step"), x.get("step")) if len(steps) > 1 else None,
                        "used": x.get("used") or {}, "downloads": x.get("downloads") or []})
    end = next((x for x in reversed(lines) if x.get("kind") == "flow_end"), None)
    return {"run_id": run_dir.name, "dir": run_dir, "ts": lines[0].get("ts") if lines else "",
            "name": flow.get("name") or "", "question": str(inputs.get("pregunta") or inputs.get("input") or ""),
            "chat_id": str(gw.get("chat_id") or ""), "files": gw.get("files") or [], "modes": gw.get("modes") or [],
            "answers": answers, "status": end.get("status") if end else None,
            "hash": lines[-1].get("hash") if lines else "", "task": gw.get("task") or ""}


def _local(ts: str, run_id: str = "") -> datetime | None:
    """The journal's UTC time, or the run id's local one, as Iván's local time."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    except ValueError:
        pass
    try:
        return datetime.strptime(run_id[:15], "%Y%m%d-%H%M%S")
    except ValueError:
        return None


def _when(ts: str, run_id: str = "") -> str:
    t = _local(ts, run_id)
    return t.strftime("%d/%m/%Y %H:%M") if t else ""


def _day(ts: str, run_id: str = "") -> str:
    t = _local(ts, run_id)
    return t.strftime("%Y-%m-%d") if t else time.strftime("%Y-%m-%d")


def _failed(code: str | None, label: str) -> str:
    return f"*(Sin respuesta. {PROBLEMS.get(code or '', DEFAULT)[0].format(ai=label)}.)*"


def _explain(exc: Exception) -> str:
    """The last failure, as the app shows it ("Último fallo: …")."""
    if isinstance(exc, OSError):
        return f"no se pudo escribir en la carpeta ({exc.strerror or type(exc).__name__})"
    return f"fallo interno de webllm ({type(exc).__name__})"


def render(conv: dict[str, Any], runs: list[dict[str, Any]], labels: dict[str, str], copies: dict[str, str]) -> str:
    """The note of one conversation, from the journal only. Every answer is its response file, verbatim."""
    up = "../"  # a note lives in webllm/<Proyecto>/
    out = ["---", "webllm: conversación", f"proyecto: {json.dumps(conv['project'], ensure_ascii=False)}",
           f"creada: {_when(conv['created'], conv['runs'][0] if conv['runs'] else '')}", f"clave: {conv['key']}",
           "---", "", f"# {conv['title']}", ""]
    for r in runs:
        out += [f"## Tú · {_when(r['ts'], r['run_id'])}", "", r["question"].rstrip() or "(sin texto)", ""]
        for f in r["files"]:
            name = str(f.get("name"))
            where = copies.get(f"{r['run_id']}/{f.get('sha256')}")
            out.append(f"- Adjunto: {_link(name, up + where) if where else f'«{name}»'} "
                       f"(huella `{str(f.get('sha256'))[:12]}`)")
        if r["modes"]:
            out.append(f"- Modos pedidos: {', '.join(r['modes'])}")
        if r["files"] or r["modes"]:
            out.append("")
        for a in r["answers"]:
            used = a["used"] or {}
            what = [f"paso «{a['step']}»" if a["step"] else None,
                    f"modelo «{used['model']}»" if used.get("model") else None,
                    ", ".join(f"«{m.get('name') or m.get('mode')}»" for m in used.get("modes") or []) or None]
            label = labels.get(a["provider"] or "", a["provider"] or "?")
            head = f"## {label}" + "".join(f" · {w}" for w in what if w)
            if a["seconds"] is not None:
                head += f" · {round(float(a['seconds']))} s"
            out += [head, ""]
            if a["status"] == "ok":
                out += [a["text"].rstrip(), ""]
            else:
                out += [_failed(a["code"], label), ""]
            for d in a["downloads"]:
                where = copies.get(f"{r['run_id']}/{d.get('sha256')}")
                if where:
                    out.append(f"- Generó: {_link(str(d.get('name')), up + where)}")
                elif d.get("url"):
                    out.append(f"- Dejó en su web: [{d.get('name')}]({d['url']})")
                elif d.get("sha256"):
                    out.append(f"- Generó «{d.get('name')}» (está en webllm, en data\\descargas)")
            if a["downloads"]:
                out.append("")
        if r["status"] is None:
            out += ["*(esperando la respuesta…)*", ""]
        out += [f"<small>Registro de webllm: {r['run_id']} · sello `{str(r['hash'])[:16]}`</small>", ""]
    return "\n".join(out).rstrip() + "\n"


def render_index(convs: list[dict[str, Any]]) -> str:
    out = ["---", "webllm: índice", "---", "", "# Conversaciones de webllm", "",
           "Lo escribe webllm solo; no lo edites (se reescribe).", ""]
    by_project: dict[str, list[dict[str, Any]]] = {}
    for c in convs:
        by_project.setdefault(c["project"], []).append(c)
    for project in sorted(by_project, key=lambda p: (p in (NO_PROJECT, APP_PROJECT), p.lower())):
        out += [f"## {project}", ""]
        for c in sorted(by_project[project], key=lambda c: c.get("updated", ""), reverse=True):
            n = len(c["runs"])
            out.append(f"- {_link(c['title'], c['note'])} · {_when(c.get('updated', ''), c['runs'][-1] if n else '')}"
                       f" · {n} {'pregunta' if n == 1 else 'preguntas'}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ------------------------------------------------------------------ the one writer

class _Writer:
    """One background thread writes the vault, in order. flush() waits until everything asked is written."""

    def __init__(self) -> None:
        self.jobs: collections.deque[tuple[Any, ...]] = collections.deque()
        self.cv = threading.Condition()
        self.busy = False
        self.thread: threading.Thread | None = None

    def submit(self, job: tuple[Any, ...]) -> None:
        with self.cv:
            self.jobs.append(job)
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._loop, name="webllm-vault", daemon=True)
                self.thread.start()
            self.cv.notify_all()

    def flush(self, timeout: float = 10.0) -> bool:
        with self.cv:
            return self.cv.wait_for(lambda: not self.jobs and not self.busy, timeout)

    def _loop(self) -> None:
        while True:
            with self.cv:
                self.cv.wait_for(lambda: bool(self.jobs))
                job = self.jobs.popleft()
                self.busy = True
            try:
                _do(*job)
            except Exception:  # noqa: BLE001 - _do records its own errors; this thread must never die
                pass
            finally:
                with self.cv:
                    self.busy = False
                    self.cv.notify_all()


_WORKER = _Writer()


def export_run(paths: "Paths", run_dir: Path, *, labels: dict[str, str] | None = None, project: str | None = None,
               title: str | None = None) -> None:
    """Ask for the note of the conversation this run belongs to (and the index) to be written again, whole.
    Called as things happen: when a question is recorded and when each answer is. Returns at once; never
    raises: the memory must never hold up or break a question."""
    try:
        if settings(paths)["enabled"]:
            _WORKER.submit(("run", paths, run_dir, labels, project, title))
    except Exception:  # noqa: BLE001
        pass


def write_committee(paths: "Paths", title: str, text: str) -> Path | None:
    """The Committee's document (F7): <vault>/webllm/Comités/AAAA-MM-DD <tema>.md, written whole.
    Returns where it will be (the writer writes it in turn), or None when the memory is off."""
    s = settings(paths)
    if not s["enabled"]:
        return None
    with _INDEX_LOCK:
        index = _read_json(paths.state_dir / INDEX)
        taken = set(index.setdefault("committees", []))
        stem = f"{time.strftime('%Y-%m-%d')} {safe_name(title)}"
        name = f"{stem}.md"
        for n in range(2, 1000):
            if name not in taken:
                break
            name = f"{stem} ({n}).md"
        index["committees"].append(name)
        _write_json(paths.state_dir / INDEX, index)
    _WORKER.submit(("doc", paths, f"Comités/{name}", text, None, None))
    return Path(s["dir"]) / ROOT / "Comités" / name


def flush(timeout: float = 10.0) -> bool:
    """Wait until everything asked so far is written (tests; the bridge before it closes)."""
    return _WORKER.flush(timeout)


def conversations(paths: "Paths") -> int:
    return len(_read_json(paths.state_dir / INDEX).get("conversations") or {})


def retry(paths: "Paths") -> None:
    """Write again everything that could not be written (the app asks when it shows a failure)."""
    if settings(paths)["enabled"]:
        _WORKER.submit(("all", paths, None, None, None, None))


def _do(kind: str, paths: "Paths", a: Any, b: Any, c: Any, d: Any) -> None:
    s = settings(paths)
    if not s["enabled"]:
        return  # turned off after it was asked: nothing more is written
    folder = s["dir"]
    base = Path(folder) / ROOT
    failed_before = bool(s.get("error"))
    error = None
    try:
        conv = _remember(paths, folder, a, b, c, d) if kind == "run" else None  # webllm's own: always
        if kind == "doc":
            with _INDEX_LOCK:
                index = _index_for(paths, folder)
                index.setdefault("pending_docs", {})[a] = b  # kept until it is really in the vault
                _write_json(paths.state_dir / INDEX, index)
        if not Path(folder).is_dir():  # Drive closed, or the vault moved: never recreate it somewhere else
            raise _Gone()
        if kind == "all" or failed_before:
            _export_all(paths, base, folder)  # after a failure: whatever it missed, too
        elif kind == "doc":
            _write_pending_docs(paths, base, folder)
        elif conv is not None:
            _write_conversation(paths, base, folder, conv)
            _write_index(paths, base, folder)
    except _Gone:
        error = "la carpeta del vault no está (¿Google Drive cerrado, o la moviste?)"
    except Exception as exc:  # noqa: BLE001 - shown in the app ("Último fallo"), never breaks an answer
        error = _explain(exc)
    _write_json(paths.state_dir / STATUS, {"dir": s["dir"], "last": time.strftime("%Y-%m-%d %H:%M:%S"),
                                           "error": error})


class _Gone(Exception):
    pass


def _index_for(paths: "Paths", folder: str) -> dict[str, Any]:
    index = _read_json(paths.state_dir / INDEX)
    if index.get("dir") != folder:  # a new vault: what was copied into the old one must be copied again
        index["dir"], index["copied"] = folder, {}
    for k in ("labels", "conversations", "copied"):
        index.setdefault(k, {})
    return index


def _remember(paths: "Paths", folder: str, run_dir: Path, labels: dict[str, str] | None, project: str | None,
              title: str | None) -> dict[str, Any] | None:
    """Put this run in its conversation, in webllm's own index; the conversation, or None (not a question)."""
    run = _run(run_dir)
    if run is None or run["task"]:
        return None  # not a question (Open WebUI's internal jobs are not conversations)
    if title and title.strip().lower() in PLACEHOLDER_TITLES:
        title = None  # Open WebUI's "New Chat": the first question names it better
    with _INDEX_LOCK:
        index = _index_for(paths, folder)
        index["labels"].update(labels or {})  # the names Iván knows, kept from the calls that bring them
        convs: dict[str, Any] = index["conversations"]
        key = f"owui:{run['chat_id']}" if run["chat_id"] else f"run:{run['run_id']}"
        conv = convs.get(key)
        if conv is None:
            proj = safe_name(project or (NO_PROJECT if run["chat_id"] else APP_PROJECT), 60)
            name = safe_name(title or run["question"].split("\n")[0] or run["name"] or "Conversación")
            stem = f"{_day(run['ts'], run['run_id'])} {name}"
            taken = {c["note"].lower() for c in convs.values()}  # webllm's own names: the vault is never listed
            note = f"{proj}/{stem}.md"
            for n in range(2, 1000):
                if note.lower() not in taken:
                    break
                note = f"{proj}/{stem} ({n}).md"
            conv = convs[key] = {"key": key, "project": proj, "title": (title or name)[:120], "note": note,
                                 "created": run["ts"], "runs": []}
        if title and title[:120] != conv["title"]:
            conv["title"] = title[:120]  # the file keeps its name, so links to it stay valid
        if run["run_id"] not in conv["runs"]:
            conv["runs"].append(run["run_id"])
        conv["updated"] = run["ts"] or conv.get("updated", "")
        _write_json(paths.state_dir / INDEX, index)
    return dict(conv)


def _export_all(paths: "Paths", base: Path, folder: str) -> None:
    with _INDEX_LOCK:
        convs = list(_index_for(paths, folder)["conversations"].values())
    for conv in convs:
        _write_conversation(paths, base, folder, conv)
    _write_index(paths, base, folder)
    _write_pending_docs(paths, base, folder)


def _write_pending_docs(paths: "Paths", base: Path, folder: str) -> None:
    with _INDEX_LOCK:
        docs = dict(_index_for(paths, folder).get("pending_docs") or {})
    for rel, text in docs.items():
        _put(base, rel, text)
        with _INDEX_LOCK:
            index = _index_for(paths, folder)
            index.get("pending_docs", {}).pop(rel, None)
            _write_json(paths.state_dir / INDEX, index)


def _write_conversation(paths: "Paths", base: Path, folder: str, conv: dict[str, Any]) -> None:
    runs = [r for r in (_run(paths.runs_dir / rid) for rid in conv["runs"]) if r is not None]
    copies = _copy_files(paths, base, folder, runs)
    with _INDEX_LOCK:
        labels = dict(_index_for(paths, folder)["labels"])
    _put(base, conv["note"], render(conv, runs, labels, copies))


def _write_index(paths: "Paths", base: Path, folder: str) -> None:
    with _INDEX_LOCK:
        convs = list(_index_for(paths, folder)["conversations"].values())
    _put(base, "Índice.md", render_index(convs))


def _copy_files(paths: "Paths", base: Path, folder: str, runs: list[dict[str, Any]]) -> dict[str, str]:
    """Iván's files and what a chat produced go next to the notes (Adjuntos/<run>/), so they open in Obsidian,
    on the phone too. Each is copied once, from webllm's own copy, and only if it still has its journal
    fingerprint; the vault is never looked at."""
    with _INDEX_LOCK:
        copied: dict[str, str] = dict(_index_for(paths, folder)["copied"])
    wanted = []
    for r in runs:
        for f in r["files"]:
            wanted.append((r, f.get("name"), f.get("sha256"), r["dir"] / str(f.get("file") or "")))
        for a in r["answers"]:
            for d in a["downloads"]:
                if d.get("path"):
                    wanted.append((r, d.get("name"), d.get("sha256"), Path(str(d["path"]))))
    new: dict[str, str] = {}
    for r, name, sha, src in wanted:
        key = f"{r['run_id']}/{sha}"
        if not sha or key in copied or key in new:
            continue
        try:
            if not src.is_file() or src.stat().st_size > MAX_ATTACHMENT:
                continue
            data = src.read_bytes()
        except OSError:
            continue
        if hashlib.sha256(data).hexdigest() != sha:
            continue  # changed since it was recorded: the vault only gets what the journal vouches for
        rel = f"Adjuntos/{r['run_id']}/{safe_name(str(name), 100)}"
        used = {*copied.values(), *new.values()}
        stem, dot, ext = rel.rpartition(".") if "." in rel.rsplit("/", 1)[-1] else (rel, "", "")
        for n in range(2, 100):  # two different files with the same name in one question
            if rel not in used:
                break
            rel = f"{stem}-{n}{dot}{ext}"
        _put(base, rel, data)
        new[key] = rel
    if new:
        with _INDEX_LOCK:
            index = _index_for(paths, folder)
            index["copied"].update(new)
            _write_json(paths.state_dir / INDEX, index)
    return {**copied, **new}


__all__ = ["APP_PROJECT", "NO_PROJECT", "configure", "conversations", "export_run", "flush", "render", "retry",
           "safe_name", "settings", "write_committee"]
