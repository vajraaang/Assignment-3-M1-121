import re
from functools import lru_cache

from nltk.stem import PorterStemmer


_token_re = re.compile(r"[A-Za-z0-9]+")
_stemmer = PorterStemmer()


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return _token_re.findall(text.lower())


@lru_cache(maxsize=500_000)
def stem(token: str) -> str:
    return _stemmer.stem(token)


def tokenize_and_stem(text: str) -> list[str]:
    return [stem(t) for t in tokenize(text)]

