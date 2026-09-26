"""Memory in Obsidian with ONE writer (PLAN-v5 D5, F5): webllm's journal is the truth; the vault is a copy,
written one way, as things happen, and NEVER read back: no note is opened and no folder is listed. The only
look is whether the vault folder itself is still there, so webllm never recreates it where Iván moved it from.

    data/state/vault.json         where the vault is and whether it is on (this PC's setting, not in git)
    data/state/vault_status.json  the last write and its error, if any (only the writer writes it)
    data/state/vault_index.json   what webllm wrote and where: conversation -> note, its runs, its title

Everything goes under <vault>/webllm/ so it never touches Iván's own notes:

    <vault>/webllm/<Proyecto>/<AAAA-MM-DD> <título>.md   one note per conversation (Open WebUI chat, or one
                                                         question/chain from webllm's app), rebuilt each time
    <vault>/webllm/Respuestas/<IA>/<AAAA-MM-DD HH.MM.SS> <IA> - <pregunta>.md
                                                         each answer of each AI on its own, written once
                                                         (Iván's decision, 26-sep-2026: his conversation
                                                         database, embedded with LM Studio)
    <vault>/webllm/Comités/                              the Committee's documents (F7)
    <vault>/webllm/Adjuntos/<run>/                       Iván's files and what a chat produced
    <vault>/webllm/Índice.md                             every conversation, by project

A conversation note is rebuilt whole from the journal each time and replaced in one go (temp file + rename),
so Drive never syncs half a file and the note always matches the journal. An answer file is written once and
never touched again (only "Reescribir todo", Iván's gesture, writes it again).
Answers are untrusted text (rule 5): what Obsidian plugins could run on their own (Templater's "<%", Dataview's
code blocks and "$=" queries) is defused in the vault copy and the note says so; the journal keeps the original,
with the same fingerprint. All writing happens in one background
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
APP_PROJECT = "Desde webllm"  # asked from webllm itself: its app, PREGUNTAR, a chain
WEB_PROJECT = "Escritas en la web"  # conversations Iván registered himself in a chat's page (PLAN-v5 F6)
MAX_ATTACHMENT = 25 * 1024 * 1024
PLACEHOLDER_TITLES = {"new chat", "nuevo chat", "nueva conversación", "nueva conversacion", "chat", "untitled"}
RUN_ID = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")
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
        for attempt in range(8):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:  # Windows: someone has it open right now (webllm's app, Drive, Obsidian)
                if attempt == 7:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ------------------------------------------------------------------ a run, read from the journal

def _run(run_dir: Path) -> dict[str, Any] | None:
    """A run as the vault needs it: a chain or a question (flow.json), or one from PREGUNTAR / the panel
    (prompt.txt, answers without a "kind")."""
    try:
        if (run_dir / "flow.json").exists():
            flow = json.loads((run_dir / "flow.json").read_text(encoding="utf-8"))
        elif (run_dir / "prompt.txt").exists():
            flow = {"name": "Pregunta a varias IAs", "inputs": {"pregunta": (run_dir / "prompt.txt").read_text(encoding="utf-8")}}
        else:
            return None
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
    gw = next((x for x in lines if x.get("kind") in ("gateway", "observed")), {})
    answers = []
    for x in lines:
        if x.get("kind", "flow") != "flow" or not x.get("provider"):
            continue
        text = ""
        if x.get("response_file"):
            try:
                text = (run_dir / x["response_file"]).read_text(encoding="utf-8")
            except OSError:
                text = ""
        answers.append({"provider": x.get("provider"), "model": x.get("model"), "status": x.get("status"),
                        "code": x.get("code"), "text": text, "seconds": x.get("latency_s"), "key": x.get("hash"),
                        "ts": x.get("ts") or "", "sha256": x.get("response_sha256"),
                        "step": steps.get(x.get("step"), x.get("step")) if len(steps) > 1 else None,
                        "used": x.get("used") or {}, "downloads": x.get("downloads") or [], "by": x.get("by")})
    end = next((x for x in reversed(lines) if x.get("kind") == "flow_end"), None)
    return {"run_id": run_dir.name, "dir": run_dir, "ts": lines[0].get("ts") if lines else "",
            "name": flow.get("name") or "", "question": str(inputs.get("pregunta") or inputs.get("input") or ""),
            "chat_id": str(gw.get("chat_id") or ""), "files": gw.get("files") or [], "modes": gw.get("modes") or [],
            "answers": answers, "status": end.get("status") if end else ("hecha" if (run_dir / "run.json").exists() else None),
            "hash": lines[-1].get("hash") if lines else "", "task": gw.get("task") or "",
            "project": gw.get("project") or None, "title": gw.get("title") or None,
            # PLAN-v5 F6: a turn Iván wrote himself in the chat's page, and the conversation it goes on with
            "observed": gw.get("kind") == "observed", "follows": gw.get("follows_root") or gw.get("follows") or None}


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


_DEFUSE = (  # (what, pattern, replacement, how to undo it)
    ("etiquetas de Templater", re.compile(r"<%"), "<\\%", (re.compile(r"<\\%"), "<%")),
    ("bloques de Dataview", re.compile(r"^([ \t>]*(?:```|~~~)[ \t]*)(dataviewjs|dataview)\b", re.M | re.I),
     r"\1webllm-\2", (re.compile(r"^([ \t>]*(?:```|~~~)[ \t]*)webllm-(dataviewjs|dataview)\b", re.M | re.I), r"\1\2")),
    ("consultas en línea de Dataview", re.compile(r"`\$="), "`$\\=", (re.compile(r"`\$\\="), "`$=")),
)


def defuse(text: str) -> tuple[str, list[str]]:
    """What an Obsidian plugin could run by itself when the file appears or is opened, made inert (visibly)."""
    done = []
    for what, pattern, repl, _ in _DEFUSE:
        text, n = pattern.subn(repl, text)
        if n:
            done.append(what)
    return text, done


def undo_defuse(text: str) -> str:
    for _, _, _, (pattern, repl) in reversed(_DEFUSE):
        text = pattern.sub(repl, text)
    return text


def _stamp(ts: str, run_id: str = "") -> datetime:
    return _local(ts, run_id) or datetime.now()


def answer_name(ts: str, label: str, question: str, step: str | None = None) -> str:
    """«2026-09-26 14.05.12 Qwen - ¿Qué es la inflación»: the date first (they sort by time), then who and what.
    Short enough for Windows' 260-character paths with the vault a few folders deep."""
    what = safe_name(step or question.split("\n")[0] or "respuesta", 60)
    return safe_name(f"{_stamp(ts):%Y-%m-%d %H.%M.%S} {label} - {what}", 100)


def _yaml(value: Any) -> str:
    """A value for the note's properties: JSON is valid YAML, except for the line breaks YAML 1.1 has and JSON
    leaves as they are."""
    return json.dumps(value, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029") \
        .replace("\x85", "\\u0085")


def _model(a: dict[str, Any]) -> str | None:
    """The model that really answered: read on the chat's page (F4), or the API's own answer; a chat whose page
    did not say has none (never "browser/qwen")."""
    used = (a.get("used") or {}).get("model")
    if used:
        return str(used)
    model = str(a.get("model") or "")
    return model if model and not model.startswith("browser/") else None


def render_answer(conv: dict[str, Any], r: dict[str, Any], a: dict[str, Any], label: str) -> str:
    """One answer on its own: when, who, with what, the question, and the answer exactly as the journal has it."""
    used = a["used"] or {}
    text, defused = defuse(a["text"])
    fm = ["---", "webllm: respuesta", f"fecha: {_stamp(a['ts'], r['run_id']):%Y-%m-%dT%H:%M:%S}",
          f"ia: {_yaml(label)}"]
    if _model(a):
        fm.append(f"modelo: {_yaml(_model(a))}")
    modes = [m.get("name") or m.get("mode") for m in used.get("modes") or []]
    if modes:
        fm.append(f"modos: {_yaml(modes)}")
    if a["step"]:
        fm.append(f"paso: {_yaml(a['step'])}")
    fm += [f"proyecto: {_yaml(conv['project'])}",
           f"conversacion: {_yaml(conv['title'])}",
           f"pregunta: {_yaml(' '.join(r['question'].split())[:300])}",
           f"registro: {r['run_id']}", f"huella: {a['sha256']}"]
    if a.get("by") == "ivan":
        fm.append(f"escrita_en: {_yaml(f'la web de {label}, siguiendo tú la conversación')}")
    if defused:
        fm.append(f"desactivado: {_yaml(defused)}")
    fm.append("---")
    head = (f"# {_stamp(a['ts'], r['run_id']):%Y-%m-%d %H:%M} · {label}" + (f" · paso «{a['step']}»" if a["step"] else "")
            + (" · en su web" if a.get("by") == "ivan" else ""))
    body = [head, "", f"De la conversación {_link(conv['title'], '../../' + conv['note'])}.", ""]
    if defused:
        body += [f"> webllm desactivó aquí {', '.join(defused)} para que ningún complemento de Obsidian lo ejecute "
                 "solo; el original está en el registro de webllm, con la misma huella.", ""]
    body += ["## Pregunta", "", *[f"> {x}".rstrip() for x in (r["question"].strip() or "(sin texto)").split("\n")], "",
             "## Respuesta", "", ""]
    return "\n".join(fm + [""] + body) + text


def render(conv: dict[str, Any], runs: list[dict[str, Any]], labels: dict[str, str], copies: dict[str, str],
           own: dict[str, str] | None = None) -> str:
    """The note of one conversation, from the journal only. Every answer is its response file, verbatim (with
    what a plugin could run defused); ``own`` = each answer's own file."""
    own = own or {}
    up = "../"  # a note lives in webllm/<Proyecto>/
    out = ["---", "webllm: conversación", f"proyecto: {_yaml(conv['project'])}",
           f"creada: {_when(conv['created'], conv['runs'][0] if conv['runs'] else '')}", f"clave: {conv['key']}",
           "---", "", f"# {conv['title']}", "",
           "> Esta nota la escribe webllm y la rehace con cada respuesta: lo que cambies aquí se pierde. Cada "
           "respuesta está también en su propio archivo, que webllm no vuelve a tocar.", ""]
    for r in runs:
        where = ""
        if r["observed"] and r["answers"]:
            where = f", en la web de {labels.get(r['answers'][0]['provider'] or '', r['answers'][0]['provider'] or '?')}"
        out += [f"## Tú{where} · {_when(r['ts'], r['run_id'])}", "", r["question"].rstrip() or "(sin texto)", ""]
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
                    f"modelo «{_model(a)}»" if _model(a) and a["status"] == "ok" else None,
                    ", ".join(f"«{m.get('name') or m.get('mode')}»" for m in used.get("modes") or []) or None]
            label = labels.get(a["provider"] or "", a["provider"] or "?")
            if a.get("by") == "ivan":
                what.insert(0, "en su web")
            head = f"## {label}" + "".join(f" · {w}" for w in what if w)
            if a["seconds"] is not None:
                head += f" · {round(float(a['seconds']))} s"
            out += [head, ""]
            if a["status"] == "ok":
                text, defused = defuse(a["text"])
                out += [text.rstrip(), ""]
                if defused:
                    out += [f"<small>webllm desactivó aquí {', '.join(defused)}; el original está en su registro."
                            "</small>", ""]
                if own.get(a["key"]):
                    out += [f"<small>En su propio archivo: {_link(Path(own[a['key']]).stem, up + own[a['key']])}</small>", ""]
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
    _WORKER.submit(("doc", paths, f"Comités/{name}", defuse(text)[0], None, None))  # written by AIs, too
    return Path(s["dir"]) / ROOT / "Comités" / name


def flush(timeout: float = 10.0) -> bool:
    """Wait until everything asked so far is written (tests; the bridge before it closes)."""
    return _WORKER.flush(timeout)


def conversations(paths: "Paths") -> int:
    return len(_read_json(paths.state_dir / INDEX).get("conversations") or {})


def rewrite_all(paths: "Paths") -> None:
    """"Reescribir todo" (Iván's gesture): every conversation, every answer and every file written again from
    the journal, even the ones already there (what he changed by hand in them is lost; he is told first)."""
    if not settings(paths)["enabled"]:
        return
    with _INDEX_LOCK:
        index = _read_json(paths.state_dir / INDEX)
        index["copied"], index["answers_done"] = {}, {}
        _write_json(paths.state_dir / INDEX, index)
    _WORKER.submit(("all", paths, None, None, None, None))


def import_history(paths: "Paths", labels: dict[str, str] | None = None) -> None:
    """"Copiar también lo de antes" (Iván's gesture): every question in webllm's record from before the memory
    was on, into its conversation, in time order."""
    if settings(paths)["enabled"]:
        _WORKER.submit(("history", paths, labels, None, None, None))


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
        if kind == "history":
            _history(paths, folder, a)
        if kind in ("all", "history") or failed_before:
            _export_all(paths, base, folder)  # after a failure: whatever it missed, too
        elif kind == "doc":
            _write_pending_docs(paths, base, folder)
        elif conv is not None:
            _write_one(paths, base, folder, conv)
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
    if index.get("dir") != folder:  # a new vault: what was written into the old one must be written again
        index["dir"], index["copied"], index["answers_done"] = folder, {}, {}
    for k in ("labels", "conversations", "copied", "answers", "answers_done"):
        index.setdefault(k, {})
    return index


def _remember(paths: "Paths", folder: str, run_dir: Path, labels: dict[str, str] | None, project: str | None,
              title: str | None) -> dict[str, Any] | None:
    """Put this run in its conversation, in webllm's own index; the conversation, or None (not a question)."""
    with _INDEX_LOCK:
        index = _index_for(paths, folder)
        index["labels"].update(labels or {})  # the names Iván knows, kept from the calls that bring them
        conv = _remember_in(index, run_dir, project, title)
        _write_json(paths.state_dir / INDEX, index)
    return dict(conv) if conv else None


def _remember_in(index: dict[str, Any], run_dir: Path, project: str | None, title: str | None) -> dict[str, Any] | None:
    run = _run(run_dir)
    if run is None or run["task"]:
        return None  # not a question (Open WebUI's internal jobs are not conversations)
    project, title = project or run["project"], " ".join(str(title or run["title"] or "").split()) or None
    if title and title.lower() in PLACEHOLDER_TITLES:
        title = None  # Open WebUI's "New Chat": the first question names it better
    convs: dict[str, Any] = index["conversations"]
    key = (f"owui:{run['chat_id']}" if run["chat_id"] else f"run:{run['follows']}" if run["follows"]
           else f"run:{run['run_id']}")
    conv = convs.get(key)
    if conv is None:
        proj = safe_name(project or (NO_PROJECT if run["chat_id"] else WEB_PROJECT if run["observed"] and not run["follows"]
                                     else APP_PROJECT), 60)
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
    # in the order they were asked, even when older questions are copied later ("Copiar también lo de antes"):
    # by the journal's first line (milliseconds; a run id only has seconds and then a random part)
    when = conv.setdefault("when", {})
    when[run["run_id"]] = run["ts"] or when.get(run["run_id"], "")
    if run["run_id"] not in conv["runs"]:
        conv["runs"].append(run["run_id"])
    conv["runs"] = sorted(conv["runs"], key=lambda r: when.get(r) or "~")  # one still without a line goes last
    conv["updated"] = max(run["ts"] or "", conv.get("updated", ""))
    return conv


def _history(paths: "Paths", folder: str, labels: dict[str, str] | None) -> None:
    """Every run in webllm's record into its conversation, a few hundred at a time (one index write each)."""
    runs = sorted(d for d in paths.runs_dir.iterdir() if RUN_ID.match(d.name)) if paths.runs_dir.exists() else []
    for i in range(0, max(len(runs), 1), 200):
        with _INDEX_LOCK:
            index = _index_for(paths, folder)
            index["labels"].update(labels or {})
            for d in runs[i:i + 200]:
                _remember_in(index, d, None, None)
            _write_json(paths.state_dir / INDEX, index)


class _Pending:
    """What the writer did in the vault, kept here and put into the index in one go (not once per file)."""

    def __init__(self) -> None:
        self.answers: dict[str, str] = {}  # answer -> its file (names never change)
        self.done: dict[str, bool] = {}  # answers written into this vault
        self.copied: dict[str, str] = {}  # files copied into this vault

    def save(self, paths: "Paths", folder: str) -> None:
        if not (self.answers or self.done or self.copied):
            return
        with _INDEX_LOCK:
            index = _index_for(paths, folder)
            index["answers"].update(self.answers)
            index["answers_done"].update(self.done)
            index["copied"].update(self.copied)
            _write_json(paths.state_dir / INDEX, index)
        self.answers, self.done, self.copied = {}, {}, {}


def _snapshot(paths: "Paths", folder: str) -> dict[str, Any]:
    with _INDEX_LOCK:
        return _index_for(paths, folder)


def _export_all(paths: "Paths", base: Path, folder: str) -> None:
    snap, pend = _snapshot(paths, folder), _Pending()
    try:
        for n, conv in enumerate(list(snap["conversations"].values()), start=1):
            _write_conversation(paths, base, conv, snap, pend)
            if n % 50 == 0:
                pend.save(paths, folder)
    finally:
        pend.save(paths, folder)
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


def _write_one(paths: "Paths", base: Path, folder: str, conv: dict[str, Any]) -> None:
    pend = _Pending()
    try:
        _write_conversation(paths, base, conv, _snapshot(paths, folder), pend)
    finally:
        pend.save(paths, folder)
    _write_index(paths, base, folder)


def _write_conversation(paths: "Paths", base: Path, conv: dict[str, Any], snap: dict[str, Any], pend: _Pending) -> None:
    """The conversation's note (whole, again), after its answers' own files and its attachments."""
    runs = [r for r in (_run(paths.runs_dir / rid) for rid in conv["runs"]) if r is not None]
    labels = dict(snap["labels"])
    copies = _copy_files(base, runs, {**snap["copied"], **pend.copied}, pend)
    own = _write_answers(base, conv, runs, labels, snap, pend)
    _put(base, conv["note"], render(conv, runs, labels, copies, own))


def _write_answers(base: Path, conv: dict[str, Any], runs: list[dict[str, Any]], labels: dict[str, str],
                   snap: dict[str, Any], pend: _Pending) -> dict[str, str]:
    """Each answer in its own file, named when it first arrives and written once into each vault."""
    names = {**snap["answers"], **pend.answers}
    taken = {v.lower() for v in names.values()}
    for r in runs:
        for a in r["answers"]:
            if a["status"] != "ok" or not a["key"]:
                continue
            label = labels.get(a["provider"] or "", a["provider"] or "?")
            if a["key"] not in names:
                stem = f"Respuestas/{safe_name(label, 40)}/{answer_name(a['ts'] or r['ts'], label, r['question'], a['step'])}"
                rel = f"{stem}.md"
                for n in range(2, 1000):
                    if rel.lower() not in taken:
                        break
                    rel = f"{stem} ({n}).md"
                names[a["key"]] = pend.answers[a["key"]] = rel
                taken.add(rel.lower())
            if not (snap["answers_done"].get(a["key"]) or pend.done.get(a["key"])):
                _put(base, names[a["key"]], render_answer(conv, r, a, label))
                pend.done[a["key"]] = True
    return {a["key"]: names[a["key"]] for r in runs for a in r["answers"] if a["key"] in names}


def _write_index(paths: "Paths", base: Path, folder: str) -> None:
    _put(base, "Índice.md", render_index(list(_snapshot(paths, folder)["conversations"].values())))


def _copy_files(base: Path, runs: list[dict[str, Any]], copied: dict[str, str], pend: _Pending) -> dict[str, str]:
    """Iván's files and what a chat produced go next to the notes (Adjuntos/<run>/), so they open in Obsidian,
    on the phone too. Each is copied once, from webllm's own copy, and only if it still has its journal
    fingerprint; the vault is never looked at."""
    wanted = []
    for r in runs:
        for f in r["files"]:
            wanted.append((r, f.get("name"), f.get("sha256"), r["dir"] / str(f.get("file") or "")))
        for a in r["answers"]:
            for d in a["downloads"]:
                if d.get("path"):
                    wanted.append((r, d.get("name"), d.get("sha256"), Path(str(d["path"]))))
    for r, name, sha, src in wanted:
        key = f"{r['run_id']}/{sha}"
        if not sha or key in copied:
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
        used = set(copied.values())
        stem, dot, ext = rel.rpartition(".") if "." in rel.rsplit("/", 1)[-1] else (rel, "", "")
        for n in range(2, 100):  # two different files with the same name in one question
            if rel not in used:
                break
            rel = f"{stem}-{n}{dot}{ext}"
        _put(base, rel, data)
        copied[key] = pend.copied[key] = rel
    return copied


def answers(paths: "Paths") -> int:
    return len(_read_json(paths.state_dir / INDEX).get("answers") or {})


__all__ = ["APP_PROJECT", "NO_PROJECT", "WEB_PROJECT", "answer_name", "answers", "configure", "conversations", "defuse", "export_run",
           "flush", "import_history", "render", "render_answer", "retry", "rewrite_all", "safe_name", "settings",
           "undo_defuse", "write_committee"]
