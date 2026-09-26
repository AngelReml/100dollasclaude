"""PLAN-v5 F8: "Automático" and the card of each AI by API.

"Automático" (D7) chooses the AI for a question with the rules written in ``automatico.yaml``: no machine
learning, and nothing hidden. The last question Iván wrote (and the files that come with it) is read, the steps
of ``orden`` are tried one by one (the first that matches gives the type; none = a quick question), and the
question goes to the first AI of that type's list that is available right now. The first line of the answer says
what it chose and why (D21.3); a question with no signal inside a conversation goes on with the previous type.

``modelos_api.yaml`` is the card of each AI by API: who serves it, what it is good for, what it sees, its free
limits and what happens with what Iván writes. An API that may train on what he writes is never picked by
Automático or the Committee on their own until he allows it (the same rule as a web chat that is not private).
What Iván did lives in ``data/state/apis.json``: the models he turned on from OmniRoute's own list (no model id
is ever guessed here) and his privacy decisions.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import yaml

from .config import ProviderConfig

if TYPE_CHECKING:
    from .config import AppConfig, Paths

TABLE_FILE = Path(__file__).with_name("automatico.yaml")
MODELS_FILE = Path(__file__).with_name("modelos_api.yaml")
STATE_FILE = "apis.json"
TESTS_FILE = "automatico_pruebas.json"
MODEL_ID = "automatico"
LABEL = "webllm · Automático"
COMMITTEE = "comite"
DEFAULT_TYPE = "rapida"
FOLLOWS = ("codigo", "documento", "investigar")  # a question with no signal goes on with these; never the Committee
SIGNALS = ("frases", "patrones", "archivo", "largo")
FILE_KINDS = ("documento", "codigo")
IMAGES = ("si", "no", "desconocido")
PRIVACY = ("no_entrena", "sin_comprobar", "entrena_salvo_que_lo_apagues", "puede_entrenar")
PRIVATE_BY_DEFAULT = {"no_entrena": True, "sin_comprobar": True, "entrena_salvo_que_lo_apagues": False,
                      "puede_entrenar": False}
KEY = re.compile(r"^[a-z0-9][a-z0-9.-]{0,39}$")
CODE_EXT = {"py", "js", "mjs", "cjs", "ts", "tsx", "jsx", "java", "kt", "c", "h", "cpp", "hpp", "cc", "cs", "go", "rs",
            "rb", "php", "swift", "html", "htm", "css", "scss", "sql", "sh", "bash", "ps1", "bat", "cmd", "json",
            "yaml", "yml", "toml", "ipynb", "vue", "svelte", "lua", "r", "dart", "scala", "pl", "ini", "cfg"}
MAX_REASONS = 3


class AutomaticoError(ValueError):
    """A broken table or card: a programming error, never silent."""


# ---------------------------------------------------------------------------------------------- the table

@dataclass(frozen=True)
class TaskType:
    key: str
    name: str
    ruta: tuple[str, ...]
    añadidas: tuple[str, ...] = ()
    frases: tuple[tuple[str, str], ...] = ()  # (as written, compared form)
    patrones: tuple[tuple[str, re.Pattern[str]], ...] = ()
    archivo: str | None = None
    largo: int | None = None
    sin_reserva: str = ""

    @property
    def route(self) -> tuple[str, ...]:
        return (*self.ruta, *self.añadidas)

    def public(self) -> dict[str, Any]:
        return {"key": self.key, "name": self.name, "ruta": list(self.ruta), "añadidas": list(self.añadidas),
                "frases": [f for f, _ in self.frases], "archivo": self.archivo, "largo": self.largo,
                "patrones": len(self.patrones), "sin_reserva": self.sin_reserva}


@dataclass(frozen=True)
class Table:
    checked: str
    fuente: str
    orden: tuple[tuple[str, str], ...]
    tipos: dict[str, TaskType]

    def steps(self) -> list[str]:
        """The rules in plain Spanish, in the order they are tried (what the app shows)."""
        out = []
        for key, signal in self.orden:
            t = self.tipos[key]
            if signal == "frases":
                words = ", ".join(f"«{f}»" for f, _ in t.frases[:6]) + ("…" if len(t.frases) > 6 else "")
                out.append(f"Si dice {words} → {t.name}")
            elif signal == "archivo":
                out.append(f"Si adjuntas un archivo de {'código' if t.archivo == 'codigo' else 'texto (PDF, Word…)'} → {t.name}")
            elif signal == "patrones":
                out.append(f"Si lleva código escrito (un bloque ``` o algo con forma de código) → {t.name}")
            elif signal == "largo":
                out.append(f"Si tu mensaje pasa de {t.largo:,} caracteres → {t.name}".replace(",", "."))
        out.append(f"Si no, y sigues una conversación de código, documento o investigación → el mismo tipo")
        out.append(f"Si no → {self.tipos[DEFAULT_TYPE].name}")
        return out


def plain(text: str) -> str:
    """Compared form: no accents, lower case, words separated by one space."""
    t = unicodedata.normalize("NFD", text)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return " ".join(re.sub(r"[^a-z0-9+#]+", " ", t).split())


def load_table(path: Path = TABLE_FILE) -> Table:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tipos: dict[str, TaskType] = {}
    for spec in raw.get("tipos") or []:
        try:
            key = str(spec["key"])
            if key in tipos:
                raise AutomaticoError(f"tipo repetido: {key}")
            archivo = spec.get("archivo")
            if archivo is not None and archivo not in FILE_KINDS:
                raise AutomaticoError(f"{key}: archivo debe ser {FILE_KINDS}")
            patrones = []
            for src in spec.get("patrones") or []:
                try:
                    patrones.append((str(src), re.compile(str(src))))
                except re.error as exc:
                    raise AutomaticoError(f"{key}: patrón roto {src!r}: {exc}") from exc
            ruta = tuple(str(x) for x in spec.get("ruta") or ())
            added = tuple(str(x) for x in spec.get("añadidas") or ())
            if not ruta:
                raise AutomaticoError(f"{key}: sin ruta")
            if len(set(ruta + added)) != len(ruta + added):
                raise AutomaticoError(f"{key}: una IA repetida en su ruta")
            tipos[key] = TaskType(
                key=key, name=str(spec["name"]), ruta=ruta, añadidas=added,
                frases=tuple((str(f), plain(str(f))) for f in spec.get("frases") or ()),
                patrones=tuple(patrones), archivo=archivo,
                largo=int(spec["largo"]) if spec.get("largo") is not None else None,
                sin_reserva=str(spec.get("sin_reserva") or ""))
        except KeyError as exc:
            raise AutomaticoError(f"a un tipo le falta {exc}") from exc
    if DEFAULT_TYPE not in tipos:
        raise AutomaticoError(f"falta el tipo por defecto «{DEFAULT_TYPE}»")
    orden = []
    for item in raw.get("orden") or []:
        key, signal = str(item[0]), str(item[1])
        if key not in tipos or signal not in SIGNALS:
            raise AutomaticoError(f"paso de orden desconocido: {item}")
        t = tipos[key]
        if not {"frases": t.frases, "patrones": t.patrones, "archivo": t.archivo, "largo": t.largo}[signal]:
            raise AutomaticoError(f"el paso {item} usa una señal que {key} no tiene")
        orden.append((key, signal))
    return Table(checked=str(raw.get("checked") or ""), fuente=str(raw.get("fuente") or ""), orden=tuple(orden), tipos=tipos)


# ---------------------------------------------------------------------------------------------- the API cards

@dataclass(frozen=True)
class ApiModel:
    key: str
    name: str
    proveedor: str
    web: str
    familia: str
    hace: str
    contexto: str
    imagenes: str
    herramientas: str
    limites: str
    pide: str
    buscar: re.Pattern[str]
    fuente: str
    privacidad: str
    privacidad_detalle: str
    como_evitarlo: str = ""

    def public(self) -> dict[str, Any]:
        return {"key": self.key, "name": self.name, "proveedor": self.proveedor, "web": self.web, "familia": self.familia,
                "hace": self.hace, "contexto": self.contexto, "imagenes": self.imagenes, "herramientas": self.herramientas,
                "limites": self.limites, "pide": self.pide, "fuente": self.fuente,
                "privacidad": {"estado": self.privacidad, "detalle": self.privacidad_detalle, "como_evitarlo": self.como_evitarlo,
                               "privada_por_defecto": PRIVATE_BY_DEFAULT[self.privacidad]}}


def _yes_no(v: Any) -> str:
    """si / no / desconocido (YAML reads a bare «no» as false)."""
    return "si" if v is True else "no" if v is False else str(v or "desconocido")


def load_models(path: Path = MODELS_FILE) -> dict[str, ApiModel]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, ApiModel] = {}
    for spec in raw.get("modelos") or []:
        try:
            key = str(spec["key"])
            priv = spec["privacidad"]
            if not KEY.match(key) or key in out:
                raise AutomaticoError(f"clave mala o repetida: {key}")
            if priv["estado"] not in PRIVACY:
                raise AutomaticoError(f"{key}: privacidad {priv['estado']!r} no es {PRIVACY}")
            if _yes_no(spec["imagenes"]) not in IMAGES:
                raise AutomaticoError(f"{key}: imagenes debe ser {IMAGES}")
            if not PRIVATE_BY_DEFAULT[priv["estado"]] and not priv.get("como_evitarlo"):
                raise AutomaticoError(f"{key}: sin privacidad por defecto y sin decir qué puede hacer Iván")
            out[key] = ApiModel(
                key=key, name=str(spec["name"]), proveedor=str(spec["proveedor"]), web=str(spec["web"]),
                familia=str(spec["familia"]), hace=str(spec["hace"]), contexto=str(spec.get("contexto") or "sin dato"),
                imagenes=_yes_no(spec["imagenes"]), herramientas=_yes_no(spec.get("herramientas")),
                limites=str(spec["limites"]), pide=str(spec["pide"]), buscar=re.compile(str(spec["buscar"])),
                fuente=str(spec["fuente"]), privacidad=str(priv["estado"]), privacidad_detalle=str(priv["detalle"]),
                como_evitarlo=str(priv.get("como_evitarlo") or ""))
        except (KeyError, TypeError) as exc:
            raise AutomaticoError(f"a una ficha le falta {exc}") from exc
        except re.error as exc:
            raise AutomaticoError(f"búsqueda rota en una ficha: {exc}") from exc
    return out


# ---------------------------------------------------------------------------------------------- what Iván did

def load_state(paths: "Paths") -> dict[str, Any]:
    try:
        data = json.loads((paths.state_dir / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {"activos": {k: v for k, v in (data.get("activos") or {}).items() if isinstance(v, dict) and v.get("model")},
            "privacidad": {k: bool(v) for k, v in (data.get("privacidad") or {}).items() if isinstance(v, bool)}}


def _save_state(paths: "Paths", data: dict[str, Any]) -> None:
    path = paths.state_dir / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def turn_on(paths: "Paths", key: str, model: str) -> None:
    data = load_state(paths)
    data["activos"][key] = {"model": model, "when": time.strftime("%Y-%m-%d %H:%M")}
    _save_state(paths, data)


def turn_off(paths: "Paths", key: str) -> bool:
    data = load_state(paths)
    if data["activos"].pop(key, None) is None:
        return False
    _save_state(paths, data)
    return True


def set_private(paths: "Paths", key: str, allowed: bool | None) -> None:
    """Iván's word on whether Automático and the Committee may use this API on their own (None = the card's)."""
    data = load_state(paths)
    if allowed is None:
        data["privacidad"].pop(key, None)
    else:
        data["privacidad"][key] = allowed
    _save_state(paths, data)


def private_of(models: dict[str, ApiModel], state: dict[str, Any], key: str) -> bool | None:
    """May Automático and the Committee use it on their own? None = no card (it keeps what config says)."""
    if key in state["privacidad"]:
        return state["privacidad"][key]
    m = models.get(key)
    return PRIVATE_BY_DEFAULT[m.privacidad] if m else None


def with_api_models(providers: dict[str, ProviderConfig], paths: "Paths") -> dict[str, ProviderConfig]:
    """The configured AIs with each API card's privacy applied, then the APIs Iván turned on from OmniRoute."""
    models, state = load_models(), load_state(paths)
    out = {}
    for name, p in providers.items():
        if p.api_card:  # added by an earlier call: rebuilt below from what apis.json says now
            continue
        priv = private_of(models, state, name) if p.gateway == "omniroute" else None
        out[name] = replace(p, private=priv) if priv is not None and priv != p.private else p
    for key, spec in state["activos"].items():
        m = models.get(key)
        if m is None or key in out:
            continue
        out[key] = ProviderConfig(name=key, model=str(spec["model"]), kind="api", gateway="omniroute", label=m.name,
                                  private=bool(private_of(models, state, key)), api_card=True)
    return out


def candidates(models: dict[str, ApiModel], ids: list[str], blocked: Callable[[str], bool]) -> dict[str, list[str]]:
    """For each card, the model ids of OmniRoute's list that are that model (never a blocked one)."""
    out: dict[str, list[str]] = {}
    for key, m in models.items():
        hits = [i for i in ids if m.buscar.search(i.lower()) and not blocked(i)]
        out[key] = sorted(dict.fromkeys(hits))
    return out


# ---------------------------------------------------------------------------------------------- reading a question

def file_kind(name: str, mime: str) -> str:
    if str(mime).startswith("image/"):
        return "imagen"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return "codigo" if ext in CODE_EXT else "documento"


@dataclass
class Reading:
    type: str
    name: str
    why: list[str] = field(default_factory=list)
    step: int | None = None  # which step of "orden" (1-based); None = no signal
    follows: bool = False

    def why_text(self) -> str:
        if self.follows:
            return "sigue la conversación"
        if not self.why:
            return "no vi señales de los otros tipos"
        return ", ".join(self.why)


def _signal(t: TaskType, signal: str, question: str, compared: str, files: list[dict[str, Any]]) -> list[str]:
    if signal == "frases":
        hits = [f for f, c in t.frases if re.search(r"(?<![a-z0-9])" + re.escape(c) + r"(?![a-z0-9])", compared)]
        return [f"dice «{f}»" for f in hits[:MAX_REASONS]]
    if signal == "archivo":
        hits = [f["name"] for f in files if file_kind(str(f.get("name") or ""), str(f.get("mime") or "")) == t.archivo]
        return [f"adjuntaste «{n}»" for n in hits[:MAX_REASONS]]
    if signal == "patrones":
        for src, rx in t.patrones:
            m = rx.search(question)
            if m:
                return ["lleva un bloque de código"] if src == "```" else [f"lleva código («{m.group(0).strip()[:30]}»)"]
        return []
    if signal == "largo":
        return [f"tu mensaje tiene {len(question):,} caracteres".replace(",", ".")] if t.largo and len(question) > t.largo else []
    return []


def classify(table: Table, question: str, files: list[dict[str, Any]] | None = None,
             previous: str | None = None) -> Reading:
    """The type of the question: the first step of "orden" that matches; none = the previous type of the
    conversation (code, document or research), else a quick question."""
    files = list(files or [])
    compared = plain(question)
    for n, (key, signal) in enumerate(table.orden, 1):
        why = _signal(table.tipos[key], signal, question, compared, files)
        if why:
            return Reading(key, table.tipos[key].name, why, n)
    if previous in FOLLOWS and previous in table.tipos:
        return Reading(previous, table.tipos[previous].name, follows=True)
    return Reading(DEFAULT_TYPE, table.tipos[DEFAULT_TYPE].name)


# ---------------------------------------------------------------------------------------------- choosing the AI

@dataclass
class Choice:
    reading: Reading
    provider: ProviderConfig | None  # None with committee=False: nobody available
    committee: bool = False
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (who, why not), in the list's order
    after: list[str] = field(default_factory=list)  # who comes next in the list (not tried)

    @property
    def label(self) -> str:
        from .committee import LABEL as COMMITTEE_LABEL
        return COMMITTEE_LABEL if self.committee else self.provider.display if self.provider else ""


def label_of(name: str, models: dict[str, ApiModel], catalog_name: Callable[[str], str | None]) -> str:
    if name == COMMITTEE:
        from .committee import LABEL as COMMITTEE_LABEL
        return COMMITTEE_LABEL
    if name in models:
        return models[name].name
    return catalog_name(name) or name


def choose(cfg: "AppConfig", table: Table, models: dict[str, ApiModel], reading: Reading, *,
           ready: Callable[[ProviderConfig, int], str | None], recent: Callable[[ProviderConfig], str | None],
           card: Callable[[ProviderConfig], dict[str, Any] | None], catalog_name: Callable[[str], str | None],
           files: list[dict[str, Any]] | None = None) -> Choice:
    """The first AI of the type's list that can take this question now; each one skipped says why."""
    from .appapi import site_of
    from .catalog import eligible_for_auto
    from .committee import resolve
    from .config import is_blocked_model
    files = list(files or [])
    docs = [f for f in files if file_kind(str(f.get("name") or ""), str(f.get("mime") or "")) != "imagen"]
    images = [f for f in files if file_kind(str(f.get("name") or ""), str(f.get("mime") or "")) == "imagen"]
    choice = Choice(reading, None)
    route = table.tipos[reading.type].route
    for i, name in enumerate(route):
        if name == COMMITTEE:
            choice.committee = True
            return choice
        p = resolve(cfg, name)
        label = p.display if p else label_of(name, models, catalog_name)
        why: str | None
        if p is None:
            why = "sin configurar" if name in models else "sin conectar"
        elif not p.enabled:
            why = "está apagada"
        elif is_blocked_model(cfg, p.model):
            why = "no está permitida"
        elif not eligible_for_auto(p):
            why = ("puede usar lo que escribes para entrenar: solo si la eliges tú o lo permites en su ficha"
                   if p.gateway == "omniroute" else "no es privada: solo si la eliges tú")
        else:
            why = ready(p, 1) or recent(p)
        if why is None and files:
            if site_of(p) is None:  # by API or on this PC: only images go, inside the message
                m = models.get(p.name)
                if docs:
                    why = "por API no le llegan PDF ni documentos"
                elif images and (m is None or m.imagenes != "si"):
                    why = "no ve imágenes" if m is not None and m.imagenes == "no" else "no sé si ve imágenes"
            else:
                view = card(p) or {}
                if view.get("discovered") and not view.get("files"):
                    why = "su web no tiene para subir archivos (según su ficha)"
        if why is None:
            choice.provider = p
            choice.after = [label_of(n, models, catalog_name) if resolve(cfg, n) is None else resolve(cfg, n).display
                            for n in route[i + 1:]]
            return choice
        choice.skipped.append((label, why))
    return choice


ROUTE_RE = re.compile(r"^\*\*Automático\*\* eligió \*\*(?P<who>.+?)\*\* para «(?P<type>[^»]+)»")


def route_line(choice: Choice) -> str:
    """The first line of the answer (D21.3): what it chose and why."""
    r = choice.reading
    line = f"**Automático** eligió **{choice.label}** para «{r.name}» ({r.why_text()})."
    if choice.skipped:
        line += " Antes en su lista: " + "; ".join(f"{who}, {why}" for who, why in choice.skipped) + "."
    return line


def nobody_text(choice: Choice) -> str:
    """Nobody of the list can take it: what happened and what to do (nothing was sent)."""
    r = choice.reading
    lines = [f"**Automático** no ha enviado nada: para «{r.name}» ({r.why_text()}) no hay ninguna IA disponible ahora.", ""]
    lines += [f"- {who}: {why}." for who, why in choice.skipped]
    lines += ["", "Qué puedes hacer: elige tú una IA arriba, en el selector, o conecta o configura una de esta lista "
                  "en webllm (Conectores; las de API, en su ficha de «Automático»)."]
    return "\n".join(lines)


def previous_type(table: Table, messages: list[dict[str, Any]]) -> str | None:
    """The type Automático gave to the previous question of this conversation (from its own first line)."""
    names = {t.name: k for k, t in table.tipos.items()}
    for m in reversed(messages):
        if m.get("role") != "assistant":
            continue
        text = m.get("content") if isinstance(m.get("content"), str) else ""
        hit = ROUTE_RE.match(text.strip())
        return names.get(hit.group("type")) if hit else None
    return None


def without_route_lines(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The conversation as the AIs get it: Automático's first lines are webllm's notes, not the AI's words."""
    out = []
    for m in messages:
        text = m.get("content")
        if m.get("role") == "assistant" and isinstance(text, str) and ROUTE_RE.match(text.lstrip()):
            first, _, rest = text.lstrip().partition("\n")
            m = {**m, "content": rest.lstrip("\n")}
        out.append(m)
    return out


def model_entry() -> dict[str, Any]:
    return {"id": MODEL_ID, "object": "model", "owned_by": "webllm", "name": LABEL,
            "webllm": {"kind": MODEL_ID, "label": LABEL,
                       "card": "Elige la IA según lo que preguntes, con reglas escritas que ves en webllm (Inicio → "
                               "Automático). La primera línea de cada respuesta dice qué eligió y por qué."}}


# ---------------------------------------------------------------------------------------------- Iván's test

def load_tests(paths: "Paths") -> dict[str, Any]:
    try:
        data = json.loads((paths.state_dir / TESTS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    items = [x for x in (data.get("preguntas") or []) if isinstance(x, dict) and x.get("texto")] if isinstance(data, dict) else []
    return {"preguntas": items}


def save_tests(paths: "Paths", items: list[dict[str, Any]]) -> dict[str, Any]:
    clean = []
    for x in items[:40]:
        text = str(x.get("texto") or "").strip()[:2000]
        if not text:
            continue
        mark = x.get("bien")
        clean.append({"texto": text, "tipo": str(x.get("tipo") or "")[:40], "elegida": str(x.get("elegida") or "")[:80],
                      "bien": mark if isinstance(mark, bool) else None, "cuando": time.strftime("%Y-%m-%d %H:%M")})
    path = paths.state_dir / TESTS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"preguntas": clean}, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"preguntas": clean}


__all__ = ["LABEL", "MODEL_ID", "ApiModel", "AutomaticoError", "Choice", "Reading", "Table", "TaskType", "candidates",
           "choose", "classify", "file_kind", "load_models", "load_state", "load_table", "load_tests", "model_entry",
           "nobody_text", "plain", "previous_type", "private_of", "route_line", "save_tests", "set_private", "turn_off",
           "turn_on", "with_api_models", "without_route_lines"]
