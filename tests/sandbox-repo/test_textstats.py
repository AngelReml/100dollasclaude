from textstats import word_count


def test_word_count_handles_any_whitespace():
    assert word_count("hello   world\tagain\n") == 3
