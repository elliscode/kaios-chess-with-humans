import re
from importlib import resources

BAD_WORDS = {
    line.strip()
    for line in resources.files(__package__)
        .joinpath("bad_words.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    if line.strip()
}


LEET_MAP = str.maketrans({
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "@": "a",
    "$": "s",
})

def normalize(text: str) -> str:
    text = text.lower()
    text = text.translate(LEET_MAP)
    text = re.sub(r"[^a-z0-9]", "", text)
    return text

def has_bad_word(name: str) -> bool:
    normalized = normalize(name)
    return any(word in normalized for word in BAD_WORDS)

