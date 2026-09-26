"""PLAN-v5 F3: the catalog of web chats (src/webllm_agent/catalog.yaml) and the rules that hang on it."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import make_config
from webllm_agent import catalog
from webllm_agent.appapi import SITE_URLS, parse_chat_url
from webllm_agent.config import GuardConfig, ProviderConfig, custom_provider, is_blocked_model
from webllm_agent.guard import Guard, GuardBlocked

ROOT = Path(__file__).resolve().parents[1]
CAT = catalog.load()


def test_the_catalog_has_the_27_of_the_plan():
    groups = [a.group for a in CAT.ais]
    assert len(CAT.ais) == 27 and groups.count("tuyas") == 4 and groups.count("1") == 17 and groups.count("2") == 6
    assert CAT.checked == "2026-09-25"


def test_every_address_is_https_already_normalised_and_none_repeats():
    hosts = []
    for a in CAT.ais:
        url, host = parse_chat_url(a.url)  # raises for http, a bad address or a blocked site
        assert url == a.url, (a.key, url)
        hosts.append(host)
    assert len(hosts) == len(set(hosts))


def test_none_gets_past_the_block(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [])
    for a in CAT.ais:
        assert not is_blocked_model(cfg, f"browser/{a.key}"), a.key
        assert not re.search(r"(^|\.)(claude\.ai|chatgpt\.com|openai\.com|anthropic\.com)$", parse_chat_url(a.url)[1])
    # and what the plan leaves out stays out
    left_out = ("chatgpt.com", "claude.ai", "agent.minimax.io", "manus.im", "genspark.ai", "openrouter.ai")
    assert not [a.key for a in CAT.ais if any(h in a.url for h in left_out)]


def test_every_ai_has_a_family_tags_and_what_it_is_for():
    for a in CAT.ais:
        assert a.family and a.tags and a.purpose and a.name, a.key
    assert all(a.may_fail for a in CAT.ais if a.group == "2")  # "puede fallar" says why


def test_the_built_in_ones_match_the_extension_and_the_app():
    built_in = {a.key: a.url for a in CAT.ais if a.builtin}
    assert built_in == SITE_URLS
    sites_js = (ROOT / "extension" / "sites.js").read_text("utf-8")
    assert set(re.findall(r"^  ([a-z]+): \{", sites_js, re.M)) == set(built_in)


def test_those_that_are_not_private_are_never_picked_on_their_own():
    not_private = {a.key for a in CAT.ais if not a.private}
    assert not_private == {"arena", "aistudio"}  # Arena publishes; Google AI Studio may use what you write
    for a in CAT.ais:
        p = custom_provider(a.key, a.name, a.url, catalog=True)
        assert p.private == a.private and catalog.eligible_for_auto(p) == a.private, a.key
    assert not catalog.eligible_for_auto(ProviderConfig(name="x", model="browser/x", enabled=False))


def test_sites_with_few_free_messages_have_a_lower_cap_that_the_guard_applies(tmp_path, mock_server):
    caps = {a.key: a.daily_cap for a in CAT.ais if a.daily_cap is not None}
    assert caps == {"venice": 10, "poe": 15}
    cfg = make_config(tmp_path, mock_server.base_url, [], guard=GuardConfig(min_spacing_s=0, daily_cap=150))
    guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
    venice = custom_provider("venice", "Venice", "https://venice.ai/", catalog=True)
    assert venice.daily_cap == 10

    async def spend(n):
        import asyncio
        for _ in range(n):
            guard.release(await guard.acquire(venice, notify=lambda m: None))
            await asyncio.sleep(0)

    import asyncio
    asyncio.run(spend(10))
    with pytest.raises(GuardBlocked) as exc:
        guard.check(venice)
    assert exc.value.reason == "daily_cap" and "(10 envíos)" in exc.value.message_es


def test_a_broken_catalog_is_refused(tmp_path):
    bad = tmp_path / "c.yaml"
    bad.write_text('ais:\n  - {key: a, name: A, url: "https://a.test/", group: "1", family: x, tags: [y]}\n'
                   '  - {key: a, name: B, url: "https://b.test/", group: "1", family: x, tags: [y]}\n', encoding="utf-8")
    with pytest.raises(catalog.CatalogError, match="repeated"):
        catalog.load(bad)
    bad.write_text('ais:\n  - {key: a, name: A, url: "https://a.test/", group: "9"}\n', encoding="utf-8")
    with pytest.raises(catalog.CatalogError):
        catalog.load(bad)


def test_the_catalog_ships_with_the_package():
    """ACTUALIZAR reinstalls the package: catalog.yaml must be package data, next to catalog.py."""
    assert catalog.CATALOG_FILE == ROOT / "src" / "webllm_agent" / "catalog.yaml"
    assert re.search(r'webllm_agent = \[[^\]]*"\*\.yaml"', (ROOT / "pyproject.toml").read_text("utf-8"))
