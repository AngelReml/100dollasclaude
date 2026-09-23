"""Tiny module used as the aider sandbox target."""


def word_count(text: str) -> int:
    """Return the number of words in text; words are separated by any whitespace."""
    return len(text.split(" "))
