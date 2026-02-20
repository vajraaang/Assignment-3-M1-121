import argparse
import json
import math
import sys
from bisect import bisect_left
from functools import lru_cache
from pathlib import Path

from .text import tokenize_and_stem
from .varint import decode_uvarint_from_bytes


class Lexicon:
    def __init__(self, lexicon_path: Path, prefix_path: Path, prefix_len: int):
        self.lexicon_path = lexicon_path
        self.prefix_len = prefix_len
        self.prefix_map: dict[str, tuple[int, int]] = {
            k: (v[0], v[1]) for k, v in json.loads(prefix_path.read_text(encoding="utf-8")).items()
        }
        self._f = lexicon_path.open("rb")

    def close(self) -> None:
        if not self._f.closed:
            self._f.close()

    def _key(self, term: str) -> str:
        return term[: self.prefix_len] if len(term) >= self.prefix_len else term

    @lru_cache(maxsize=256)
    def _load_bucket(self, key: str) -> tuple[list[str], list[tuple[int, int, int]]]:
        rng = self.prefix_map.get(key)
        if rng is None:
            return [], []
        start, end = rng
        if end <= start:
            return [], []
        self._f.seek(start)
        data = self._f.read(end - start).decode("utf-8", errors="strict")
        terms: list[str] = []
        meta: list[tuple[int, int, int]] = []
        for line in data.splitlines():
            if not line:
                continue
            term, off_s, len_s, df_s = line.split("\t")
            terms.append(term)
            meta.append((int(off_s), int(len_s), int(df_s)))
        return terms, meta

    def get(self, term: str) -> tuple[int, int, int] | None:
        key = self._key(term)
        terms, meta = self._load_bucket(key)
        if not terms:
            return None
        i = bisect_left(terms, term)
        if i >= len(terms) or terms[i] != term:
            return None
        return meta[i]


def load_docs(docs_path: Path) -> tuple[list[str], list[int]]:
    urls: list[str] = []
    lens: list[int] = []
    with docs_path.open("rb") as f:
        for line_b in f:
            line = line_b.decode("utf-8", errors="strict").rstrip("\n")
            if not line:
                continue
            doc_id_s, url, len_s = line.split("\t")
            doc_id = int(doc_id_s)
            doc_len = int(len_s)
            if doc_id != len(urls):
                raise ValueError("non-sequential doc ids")
            urls.append(url)
            lens.append(doc_len)
    return urls, lens


def iter_postings(block: bytes):
    pos = 0
    count, pos = decode_uvarint_from_bytes(block, pos)
    for _ in range(count):
        doc_id, pos = decode_uvarint_from_bytes(block, pos)
        tf, pos = decode_uvarint_from_bytes(block, pos)
        imp_tf, pos = decode_uvarint_from_bytes(block, pos)
        yield doc_id, tf, imp_tf


def search(index_dir: Path, query: str, top_k: int, important_boost: float) -> list[tuple[float, str]]:
    stats = json.loads((index_dir / "stats.json").read_text(encoding="utf-8"))
    prefix_len = int(stats.get("prefix_len", 3))
    urls, doc_lens = load_docs(index_dir / "docs.tsv")
    n_docs = len(urls)

    lex = Lexicon(index_dir / "lexicon.tsv", index_dir / "lexicon_prefix.json", prefix_len)
    postings_f = (index_dir / "postings.bin").open("rb")
    try:
        scores: dict[int, float] = {}
        q_terms = tokenize_and_stem(query)
        for term in q_terms:
            entry = lex.get(term)
            if entry is None:
                continue
            offset, length, df = entry
            idf = math.log((n_docs + 1) / (df + 1)) + 1.0
            postings_f.seek(offset)
            block = postings_f.read(length)
            for doc_id, tf, imp_tf in iter_postings(block):
                wtf = tf + important_boost * imp_tf
                if wtf <= 0:
                    continue
                tfw = 1.0 + math.log(wtf)
                scores[doc_id] = scores.get(doc_id, 0.0) + tfw * idf

        results: list[tuple[float, str]] = []
        for doc_id, score in scores.items():
            dl = doc_lens[doc_id] if doc_lens[doc_id] > 0 else 1
            results.append((score / math.sqrt(dl), urls[doc_id]))
        results.sort(reverse=True)
        return results[:top_k]
    finally:
        postings_f.close()
        lex.close()


def main() -> None:
    p = argparse.ArgumentParser(prog="ics_search_engine.search")
    p.add_argument("--index", required=True)
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--important-boost", type=float, default=2.0)
    p.add_argument("query", nargs="*")
    args = p.parse_args()

    index_dir = Path(args.index)
    if args.query:
        q = " ".join(args.query)
        results = search(index_dir, q, args.top_k, args.important_boost)
        for score, url in results:
            sys.stdout.write(f"{score:.6f}\t{url}\n")
        return

    try:
        while True:
            sys.stdout.write("> ")
            sys.stdout.flush()
            q = sys.stdin.readline()
            if not q:
                break
            q = q.strip()
            if not q:
                continue
            results = search(index_dir, q, args.top_k, args.important_boost)
            for score, url in results:
                sys.stdout.write(f"{score:.6f}\t{url}\n")
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
