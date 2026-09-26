"""PLAN-v5 F8: "Automático" — the table (every type has a first AI and a reserve, nothing forbidden, no web that is
not private), the API model cards, how a question is read and how the AI is chosen."""

from __future__ import annotations

import dataclasses
import re

import pytest

from webllm_agent import automatico, catalog, config
from webllm_agent.config import custom_provider, is_blocked_model

TABLE = automatico.load_table()
MODELS = automatico.load_models()
CATALOG = catalog.load()


def known(cfg, name: str) -> bool:
    return name == automatico.COMMITTEE or name in MODELS or CATALOG.get(name) is not None or name in cfg.providers


# ------------------------------------------------------------------ the table (what PLAN-v5 F8 asks to test)

def test_every_type_has_a_first_ai_and_a_reserve():
    for t in TABLE.tipos.values():
        if t.sin_reserva:  # only the Committee: it has its own reserves inside
            assert t.route == (automatico.COMMITTEE,), t.key
            continue
        assert len(t.route) >= 2, f"{t.key} no tiene reserva"


def test_nothing_in_the_table_points_to_a_forbidden_ai(tmp_path):
    cfg = config.load_config(tmp_path)
    forbidden = re.compile(r"claude|chatgpt|codex|anthropic|openai\.com")
    for t in TABLE.tipos.values():
        for name in t.route:
            assert known(cfg, name), f"{t.key}: {name} no es ninguna IA conocida"
            assert not forbidden.search(name), name
            entry = CATALOG.get(name)
            if entry is not None:
                assert not forbidden.search(entry.url), entry.url
            p = cfg.providers.get(name)
            if p is not None:
                assert not is_blocked_model(cfg, p.model), name
    # and a card never offers a blocked model from OmniRoute's list
    ids = ["cc/claude-sonnet-4.5", "cx/gpt-5-codex", "codex/glm-5.2", "nvidia/z-ai/glm-5.2", "mistral/codestral-2508"]
    offered = automatico.candidates(MODELS, ids, lambda i: is_blocked_model(cfg, i))
    assert offered["glm-5.2"] == ["nvidia/z-ai/glm-5.2"] and offered["codestral"] == ["mistral/codestral-2508"]
    assert not any("claude" in i or "codex" in i for ids_ in offered.values() for i in ids_)


def test_no_rule_uses_a_web_that_is_not_private():
    for t in TABLE.tipos.values():
        for name in t.route:
            entry = CATALOG.get(name)
            if entry is not None:
                assert entry.private, f"{t.key}: {name} no es privada"
    assert not {"arena", "aistudio"} & {n for t in TABLE.tipos.values() for n in t.route}


def test_the_rules_are_in_order_and_in_plain_spanish():
    steps = TABLE.steps()
    assert steps[0].startswith("Si dice «mi idea»") and steps[0].endswith("→ Evaluar una idea")
    assert steps[-1] == "Si no → Pregunta rápida"
    assert all("→" in s for s in steps)
    assert TABLE.orden[0] == ("idea", "frases")  # an explicit wish to evaluate wins over everything
    # what comes with the question weighs more than a loose word
    order = [f"{k}:{s}" for k, s in TABLE.orden]
    assert order.index("codigo:archivo") < order.index("codigo:frases")
    assert order.index("documento:archivo") < order.index("codigo:frases")


def test_a_broken_table_is_refused(tmp_path):
    bad = tmp_path / "t.yaml"
    bad.write_text("tipos:\n  - {key: rapida, name: R, ruta: [zai]}\norden:\n  - [codigo, frases]\n", encoding="utf-8")
    with pytest.raises(automatico.AutomaticoError):
        automatico.load_table(bad)
    bad.write_text("tipos:\n  - {key: x, name: X, ruta: [zai, zai]}\n  - {key: rapida, name: R, ruta: [zai]}\n", encoding="utf-8")
    with pytest.raises(automatico.AutomaticoError):
        automatico.load_table(bad)


# ------------------------------------------------------------------ the API cards

def test_every_api_card_says_where_its_facts_come_from_and_what_happens_with_what_you_write():
    assert {"glm-5.2", "qwen3.8-27b", "codestral", "gemini-flash", "zai"} <= set(MODELS)  # the ones PLAN-v5 F8 names
    for m in MODELS.values():
        assert m.fuente and m.proveedor and m.limites and m.privacidad_detalle
        assert m.privacidad in automatico.PRIVACY and m.imagenes in automatico.IMAGES
        if not automatico.PRIVATE_BY_DEFAULT[m.privacidad]:
            assert m.como_evitarlo, m.key  # Iván is told what he can do
    assert MODELS["codestral"].privacidad == "entrena_salvo_que_lo_apagues" and "Anonymous improvement data" in MODELS["codestral"].como_evitarlo
    assert MODELS["nemotron"].privacidad == "puede_entrenar"
    assert "Europa" in MODELS["gemini-flash"].privacidad_detalle and MODELS["gemini-flash"].imagenes == "si"


@pytest.mark.parametrize("key, hit, miss", [
    ("glm-5.2", "nvidia/z-ai/glm-5.2", "nvidia/z-ai/glm-5.21"),
    ("qwen3.8-27b", "groq/qwen/qwen3.8-27b", "groq/qwen/qwen3.8-235b"),
    ("gemini-flash", "gemini/gemini-3.5-flash", "gemini/gemini-3.5-pro"),
    ("zai", "zai/glm-4.7-flash", "zai/glm-4.6v-flash"),
])
def test_a_card_finds_its_model_in_omniroutes_list(key, hit, miss):
    got = automatico.candidates(MODELS, [hit, miss], lambda i: False)[key]
    assert got == [hit]


def test_an_api_that_may_train_is_not_used_on_its_own_until_ivan_allows_it(tmp_path):
    cfg = config.load_config(tmp_path)
    assert cfg.providers["nemotron"].private is False  # OpenRouter's free models may keep what you write
    assert cfg.providers["groq"].private is True and cfg.providers["zai"].private is True
    automatico.set_private(cfg.paths, "nemotron", True)
    assert config.load_config(tmp_path).providers["nemotron"].private is True
    automatico.set_private(cfg.paths, "nemotron", None)  # back to what its card says
    assert config.load_config(tmp_path).providers["nemotron"].private is False


def test_an_api_turned_on_from_omniroute_becomes_an_ai_and_goes_away_when_turned_off(tmp_path):
    cfg = config.load_config(tmp_path)
    automatico.turn_on(cfg.paths, "codestral", "mistral/codestral-2508")
    p = config.load_config(tmp_path).providers["codestral"]
    assert (p.display, p.gateway, p.api_card, p.private) == ("Codestral (API)", "omniroute", True, False)
    automatico.set_private(cfg.paths, "codestral", True)  # "Ya lo apagué"
    assert config.load_config(tmp_path).providers["codestral"].private is True
    automatico.turn_off(cfg.paths, "codestral")
    assert "codestral" not in automatico.with_api_models(config.load_config(tmp_path).providers, cfg.paths)


# ------------------------------------------------------------------ reading a question

PDF = {"name": "contrato.pdf", "mime": "application/pdf"}
PY = {"name": "main.py", "mime": "text/x-python"}
JPG = {"name": "foto.jpg", "mime": "image/jpeg"}


@pytest.mark.parametrize("question, files, kind, why", [
    ("¿Me arreglas este error? TypeError: cannot read properties of undefined", [], "codigo", "TypeError"),
    ("Hazme un script en Python que renombre las fotos por fecha", [], "codigo", "«script»"),
    ("```js\nconst x = 1\n```\n¿por qué falla?", [], "codigo", "bloque de código"),
    ("¿Qué hace este archivo?", [PY], "codigo", "adjuntaste «main.py»"),
    ("Resume este PDF en 5 puntos", [PDF], "documento", "adjuntaste «contrato.pdf»"),
    ("Resume este PDF que explica cómo programar en python", [PDF], "documento", "contrato.pdf"),  # the file weighs more
    ("x" * 9000, [], "documento", "9.000 caracteres"),
    ("Busca en internet las últimas noticias sobre la ley de IA, con fuentes", [], "investigar", "fuentes"),
    ("¿Qué tiempo hace hoy en Madrid?", [], "investigar", "qué tiempo hace"),
    ("¿Merece la pena montar una tienda online de cerámica?", [], "idea", "merece la pena"),
    ("Evalúa mi idea: una app para compartir coche entre vecinos", [], "idea", "mi idea"),
    ("¿Cuál es la capital de Australia?", [], "rapida", "no vi señales"),
    ("Dame una idea para cenar hoy", [], "rapida", "no vi señales"),  # "una idea" is not evaluating one
    ("¿Qué opinas de esta foto?", [JPG], "rapida", "no vi señales"),
])
def test_how_a_question_is_read(question, files, kind, why):
    r = automatico.classify(TABLE, question, files)
    assert r.type == kind and why in r.why_text(), (r.type, r.why_text())


def test_a_question_with_no_signal_goes_on_with_the_conversation():
    assert automatico.classify(TABLE, "¿y cómo lo pruebo?", [], previous="codigo").why_text() == "sigue la conversación"
    assert automatico.classify(TABLE, "¿y cómo lo pruebo?", [], previous="codigo").type == "codigo"
    assert automatico.classify(TABLE, "gracias", [], previous="idea").type == "rapida"  # never the Committee again
    assert automatico.classify(TABLE, "¿Cuál es la capital de Francia?", [], previous="rapida").type == "rapida"
    # a signal of another type wins over the conversation
    assert automatico.classify(TABLE, "busca fuentes sobre eso", [], previous="codigo").type == "investigar"


# ------------------------------------------------------------------ choosing the AI

def world(tmp_path, *, web=("kimi", "felo", "brave")):
    cfg = config.load_config(tmp_path)
    providers = dict(cfg.providers)
    for key in web:
        entry = CATALOG.get(key)
        providers[key] = custom_provider(key, entry.name, entry.url, catalog=True)
    return dataclasses.replace(cfg, providers=providers)


def pick(cfg, question, files=(), *, ready=None, recent=None, cards=None, previous=None):
    reading = automatico.classify(TABLE, question, list(files), previous)
    return automatico.choose(cfg, TABLE, MODELS, reading, ready=lambda p, n: (ready or {}).get(p.name),
                             recent=lambda p: (recent or {}).get(p.name), card=lambda p: (cards or {}).get(p.name),
                             catalog_name=lambda k: CATALOG.get(k).name if CATALOG.get(k) else None, files=list(files))


def test_the_first_available_of_the_list_is_chosen_and_each_one_before_says_why(tmp_path):
    cfg = world(tmp_path)
    c = pick(cfg, "Hazme un script en Python")
    # glm-5.2, qwen3.8-27b and codestral are not configured here: Kimi (web) is next
    assert c.provider.name == "kimi"
    assert c.skipped == [("GLM-5.2 (API)", "sin configurar"), ("Qwen3.8-27B (Groq)", "sin configurar"),
                         ("Codestral (API)", "sin configurar")]
    line = automatico.route_line(c)
    assert line.startswith("**Automático** eligió **Kimi** para «Código» (dice «script», dice «python»).")
    assert "Antes en su lista: GLM-5.2 (API), sin configurar; Qwen3.8-27B (Groq), sin configurar;" in line


def test_paused_capped_or_recently_failed_ais_are_skipped_and_said(tmp_path):
    cfg = world(tmp_path)
    c = pick(cfg, "¿Cuál es la capital de Australia?", ready={"zai": "está en pausa"}, recent={"groq": "falló hace 2 min (saturada)"})
    # qwen3.8-27b not configured, zai paused, gemini-flash not configured, groq failed a moment ago: Qwen (web)
    assert c.provider.name == "qwen"
    assert ("z.ai", "está en pausa") in c.skipped and ("groq", "falló hace 2 min (saturada)") in c.skipped


def test_an_api_that_may_train_is_skipped_until_allowed(tmp_path):
    cfg = world(tmp_path)
    automatico.turn_on(cfg.paths, "codestral", "mistral/codestral-2508")
    cfg = world(tmp_path)
    c = pick(cfg, "Hazme un script en Python")
    assert ("Codestral (API)", "puede usar lo que escribes para entrenar: solo si la eliges tú o lo permites en su ficha") in c.skipped
    automatico.set_private(cfg.paths, "codestral", True)
    assert pick(world(tmp_path), "Hazme un script en Python").provider.name == "codestral"


def test_a_pdf_never_goes_to_an_api_and_an_image_only_to_one_that_sees_images(tmp_path):
    cfg = world(tmp_path)
    automatico.turn_on(cfg.paths, "gemini-flash", "gemini/gemini-3.5-flash")
    cfg = world(tmp_path)
    c = pick(cfg, "Resume este PDF", [PDF])
    assert c.provider.name == "kimi" and ("Gemini Flash (API)", "por API no le llegan PDF ni documentos") in c.skipped
    c = pick(cfg, "¿Qué opinas de esta foto?", [JPG])
    assert c.provider.name == "gemini-flash" and ("z.ai", "no ve imágenes") in c.skipped
    # a web chat whose card says it has no way to upload files is skipped for a file
    c = pick(cfg, "Resume este PDF", [PDF], cards={"kimi": {"discovered": True, "files": []}})
    assert c.provider.name == "qwen" and ("Kimi", "su web no tiene para subir archivos (según su ficha)") in c.skipped


def test_nobody_available_sends_nothing_and_says_what_to_do(tmp_path):
    cfg = world(tmp_path, web=())
    c = pick(cfg, "Busca fuentes sobre la ley de IA")
    assert c.provider is None and not c.committee
    text = automatico.nobody_text(c)
    assert text.startswith("**Automático** no ha enviado nada") and "- Felo: sin conectar." in text and "Qué puedes hacer" in text


def test_an_idea_goes_to_the_committee(tmp_path):
    c = pick(world(tmp_path), "¿Merece la pena montar una tienda online?")
    assert c.committee and c.label == "webllm · Comité"


def test_the_first_line_is_read_back_and_kept_away_from_the_ais():
    line = "**Automático** eligió **Kimi** para «Código» (dice «script»)."
    messages = [{"role": "user", "content": "Hazme un script"}, {"role": "assistant", "content": line + "\n\nAquí tienes."},
                {"role": "user", "content": "¿y cómo lo pruebo?"}]
    assert automatico.previous_type(TABLE, messages) == "codigo"
    clean = automatico.without_route_lines(messages)
    assert clean[1]["content"] == "Aquí tienes." and clean[0] == messages[0] and messages[1]["content"].startswith("**Auto")
    assert automatico.previous_type(TABLE, [{"role": "assistant", "content": "Hola"}]) is None
