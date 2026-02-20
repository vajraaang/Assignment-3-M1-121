import argparse
import json
import shutil
import time
from collections import Counter
from heapq import heappop, heappush
from pathlib import Path

from .dataset import collect_json_files, iter_documents
from .html_extract import extract_visible_text
from .partial_index import PartialIndexIterator, write_partial_index
from .text import tokenize_and_stem
from .varint import encode_uvarint


def _compute_default_flush_docs(total_files: int, min_flushes: int, cap: int) -> int:
    if total_files <= 0:
        return 1
    docs = max(1, total_files // (min_flushes + 1))
    return min(docs, cap)


def _merge_partials(
    partial_files: list[Path],
    out_dir: Path,
    prefix_len: int,
) -> dict[str, int]:
    postings_path = out_dir / "postings.bin"
    lexicon_path = out_dir / "lexicon.tsv"
    prefix_path = out_dir / "lexicon_prefix.json"

    iters: list[PartialIndexIterator] = [PartialIndexIterator(p) for p in partial_files]
    heap: list[tuple[str, int, object]] = []

    def push_next(i: int) -> None:
        it = iters[i]
        try:
            rec = next(it)
        except StopIteration:
            it.close()
            return
        heappush(heap, (rec.term, i, rec))

    for i in range(len(iters)):
        push_next(i)

    unique_terms = 0
    prefix_map: dict[str, list[int]] = {}
    current_prefix: str | None = None
    current_prefix_start = 0

    with postings_path.open("wb") as postings_f, lexicon_path.open("wb") as lexicon_f:
        while heap:
            term, i, rec = heappop(heap)
            postings_parts = [rec.postings]
            total_count = rec.count
            push_next(i)

            while heap and heap[0][0] == term:
                _, j, rec2 = heappop(heap)
                postings_parts.append(rec2.postings)
                total_count += rec2.count
                push_next(j)

            offset = postings_f.tell()
            block = encode_uvarint(total_count) + b"".join(postings_parts)
            postings_f.write(block)
            length = len(block)

            line_start = lexicon_f.tell()
            line = f"{term}\t{offset}\t{length}\t{total_count}\n".encode("utf-8")
            lexicon_f.write(line)

            prefix = term[:prefix_len] if len(term) >= prefix_len else term
            if current_prefix is None:
                current_prefix = prefix
                current_prefix_start = line_start
            elif prefix != current_prefix:
                prefix_map[current_prefix] = [current_prefix_start, line_start]
                current_prefix = prefix
                current_prefix_start = line_start

            unique_terms += 1

        end = lexicon_f.tell()
        if current_prefix is not None:
            prefix_map[current_prefix] = [current_prefix_start, end]

    prefix_path.write_text(json.dumps(prefix_map, separators=(",", ":")), encoding="utf-8")
    return {"unique_terms": unique_terms, "lexicon_bytes": lexicon_path.stat().st_size, "postings_bytes": postings_path.stat().st_size}


def build_index(
    input_dir: Path,
    output_dir: Path,
    flush_docs: int,
    prefix_len: int,
    keep_partials: bool,
    max_docs: int | None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    partial_dir = output_dir / "partial"
    partial_dir.mkdir(parents=True, exist_ok=True)

    docs_path = output_dir / "docs.tsv"
    paths = collect_json_files(str(input_dir))

    in_memory: dict[str, list[tuple[int, int, int]]] = {}
    partial_files: list[Path] = []
    flushes = 0
    block_docs = 0
    indexed_docs = 0

    started = time.time()

    with docs_path.open("wb") as docs_f:
        for doc in iter_documents(paths):
            if max_docs is not None and doc.doc_id >= max_docs:
                break
            text, important = extract_visible_text(doc.html)
            tokens = tokenize_and_stem(text)
            important_tokens = tokenize_and_stem(important)
            tf = Counter(tokens)
            imp = Counter(important_tokens)
            doc_len = len(tokens)
            docs_f.write(f"{doc.doc_id}\t{doc.url}\t{doc_len}\n".encode("utf-8"))

            for term, count in tf.items():
                in_memory.setdefault(term, []).append((doc.doc_id, count, imp.get(term, 0)))

            indexed_docs += 1
            block_docs += 1

            if block_docs >= flush_docs:
                if in_memory:
                    part_path = partial_dir / f"partial_{flushes:04d}.bin"
                    write_partial_index(part_path, in_memory)
                    partial_files.append(part_path)
                    in_memory.clear()
                    flushes += 1
                block_docs = 0

    if in_memory:
        part_path = partial_dir / f"partial_{flushes:04d}.bin"
        write_partial_index(part_path, in_memory)
        partial_files.append(part_path)
        in_memory.clear()
        flushes += 1

    merge_stats = _merge_partials(partial_files, output_dir, prefix_len)

    if not keep_partials:
        shutil.rmtree(partial_dir, ignore_errors=True)

    elapsed_s = time.time() - started
    core_files = ["docs.tsv", "postings.bin", "lexicon.tsv", "lexicon_prefix.json"]
    core_bytes = sum((output_dir / p).stat().st_size for p in core_files)

    stats = {
        "indexed_documents": indexed_docs,
        "unique_tokens": merge_stats["unique_terms"],
        "flushes": flushes,
        "flush_docs": flush_docs,
        "prefix_len": prefix_len,
        "core_index_bytes": core_bytes,
        "core_index_kb": core_bytes / 1024.0,
        "elapsed_seconds": elapsed_s,
    }
    (output_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def main() -> None:
    p = argparse.ArgumentParser(prog="ics_search_engine.indexer")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--flush-docs", type=int, default=0)
    p.add_argument("--min-flushes", type=int, default=3)
    p.add_argument("--flush-cap", type=int, default=5000)
    p.add_argument("--prefix-len", type=int, default=3)
    p.add_argument("--keep-partials", action="store_true")
    p.add_argument("--max-docs", type=int)
    args = p.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    paths = collect_json_files(str(input_dir))
    flush_docs = args.flush_docs or _compute_default_flush_docs(len(paths), args.min_flushes, args.flush_cap)

    stats = build_index(
        input_dir=input_dir,
        output_dir=output_dir,
        flush_docs=flush_docs,
        prefix_len=max(1, args.prefix_len),
        keep_partials=bool(args.keep_partials),
        max_docs=args.max_docs,
    )
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
