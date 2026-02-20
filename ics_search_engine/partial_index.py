from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .varint import encode_uvarint, read_uvarint


@dataclass(frozen=True)
class PartialRecord:
    term: str
    count: int
    postings: bytes


def encode_postings(postings: list[tuple[int, int, int]]) -> bytes:
    out = bytearray()
    for doc_id, tf, imp_tf in postings:
        out += encode_uvarint(doc_id)
        out += encode_uvarint(tf)
        out += encode_uvarint(imp_tf)
    return bytes(out)


def write_partial_index(path: Path, terms_to_postings: dict[str, list[tuple[int, int, int]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for term in sorted(terms_to_postings.keys()):
            term_bytes = term.encode("utf-8")
            postings_list = terms_to_postings[term]
            postings_bytes = encode_postings(postings_list)
            f.write(encode_uvarint(len(term_bytes)))
            f.write(term_bytes)
            f.write(encode_uvarint(len(postings_list)))
            f.write(encode_uvarint(len(postings_bytes)))
            f.write(postings_bytes)


def _read_exact(fileobj: BinaryIO, n: int) -> bytes:
    data = fileobj.read(n)
    if len(data) != n:
        raise EOFError
    return data


class PartialIndexIterator:
    def __init__(self, path: Path):
        self.path = path
        self._f = path.open("rb")
        self._done = False

    def close(self) -> None:
        if not self._f.closed:
            self._f.close()

    def __iter__(self) -> PartialIndexIterator:
        return self

    def __next__(self) -> PartialRecord:
        if self._done:
            raise StopIteration
        try:
            term_len = read_uvarint(self._f)
        except EOFError:
            self._done = True
            raise StopIteration
        term = _read_exact(self._f, term_len).decode("utf-8", errors="strict")
        count = read_uvarint(self._f)
        postings_len = read_uvarint(self._f)
        postings = _read_exact(self._f, postings_len)
        return PartialRecord(term=term, count=count, postings=postings)

