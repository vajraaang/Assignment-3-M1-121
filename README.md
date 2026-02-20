# ICS Search Engine

Two programs:

- Indexer: builds an inverted index from the ICS crawl JSON corpus
- Search: prompts for queries and returns ranked URLs

## Dataset format

Each page is stored as a JSON file with fields:

- `url`
- `content` (HTML)
- `encoding`

The dataset root contains subfolders (one per domain). The indexer walks all `*.json` files recursively.

## Build an index

```bash
python3 -m ics_search_engine.indexer --input /path/to/analyst_or_developer --output /path/to/index_dir
```

Useful flags:

- `--flush-docs N` controls how many documents are indexed per in-memory block before flushing a partial index to disk
- `--keep-partials` keeps the flushed partial index files under `index_dir/partial/`
- `--prefix-len N` controls the lexicon prefix bucketing (default `3`)

After indexing, `index_dir/stats.json` includes:

- `indexed_documents`
- `unique_tokens`
- `core_index_kb`

## Search

Single query:

```bash
python3 -m ics_search_engine.search --index /path/to/index_dir "machine learning"
```

Interactive:

```bash
python3 -m ics_search_engine.search --index /path/to/index_dir
```

## Report (PDF + Markdown)

```bash
python3 -m ics_search_engine.report --index /path/to/index_dir
```

This writes `report.md` and `report.pdf` into the index directory.

