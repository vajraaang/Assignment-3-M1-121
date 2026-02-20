import json
import os
from pathlib import Path
from urllib.parse import urldefrag
from dataclasses import dataclass
from collections.abc import Iterable, Iterator


@dataclass(frozen=True)
class Document:
    doc_id: int
    url: str
    html: str


def collect_json_files(root: str) -> list[Path]:
    paths: list[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".json"):
                paths.append(Path(dirpath) / name)
    paths.sort()
    return paths


def iter_documents(paths: Iterable[Path]) -> Iterator[Document]:
    doc_id = 0
    for path in paths:
        try:
            with path.open("rb") as f:
                raw = f.read()
            data = json.loads(raw)
        except Exception:
            continue
        url = data.get("url")
        content = data.get("content")
        if not isinstance(url, str) or not isinstance(content, str):
            continue
        url, _ = urldefrag(url)
        yield Document(doc_id=doc_id, url=url, html=content)
        doc_id += 1
