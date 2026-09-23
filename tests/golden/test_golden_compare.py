"""Offline checks for the golden comparator (no network)."""

from golden import GOLDEN_BLOCK, GOLDEN_PROMPT, compare, is_web


def test_block_contains_all_tricky_features():
    assert "\t" in GOLDEN_BLOCK
    assert "\u00f1" in GOLDEN_BLOCK and "\u20ac" in GOLDEN_BLOCK
    assert "\n# golden" in GOLDEN_BLOCK
    assert "`x`" in GOLDEN_BLOCK and "``y``" in GOLDEN_BLOCK
    assert '\\"' in GOLDEN_BLOCK and "'" in GOLDEN_BLOCK
    assert "  \n" in GOLDEN_BLOCK
    assert GOLDEN_BLOCK in GOLDEN_PROMPT


def test_exact_echo_passes_with_outer_whitespace():
    assert compare("\n\n  " + GOLDEN_BLOCK + "\n  ")[0]


def test_lost_trailing_spaces_fail():
    ok, detail = compare(GOLDEN_BLOCK.replace("here  \n", "here\n"))
    assert not ok and "first difference" in detail


def test_tab_turned_into_spaces_fails():
    assert not compare(GOLDEN_BLOCK.replace("\t", "    "))[0]


def test_extra_preamble_fails():
    assert not compare("Here you go:\n" + GOLDEN_BLOCK)[0]


def test_web_prefix_detection():
    assert is_web("qwen-web/qwen3-max")
    assert is_web("ds-web/deepseek-chat")
    assert not is_web("groq/openai/gpt-oss-120b")
