import argparse
import json
from pathlib import Path


def _kb(value_bytes: int) -> float:
    return value_bytes / 1024.0


def render_markdown(stats: dict[str, object]) -> str:
    indexed = int(stats.get("indexed_documents", 0))
    unique = int(stats.get("unique_tokens", 0))
    size_kb = float(stats.get("core_index_kb", 0.0))
    return "\n".join(
        [
            "# Index Analytics",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Indexed documents | {indexed} |",
            f"| Unique tokens | {unique} |",
            f"| Index size on disk (KB) | {size_kb:.2f} |",
            "",
        ]
    )


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(stream: bytes) -> bytes:
    page_w = 612
    page_h = 792
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        f"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w} {page_h}] "
        f"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
    ).encode("utf-8")
    obj4 = b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    obj5 = (
        f"5 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("utf-8")
        + stream
        + b"endstream\nendobj\n"
    )

    objects = [obj1, obj2, obj3, obj4, obj5]

    pdf = bytearray()
    pdf += b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj

    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(offsets)}\n".encode("utf-8")
    pdf += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n".encode("utf-8")

    pdf += (
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "utf-8"
        )
    )
    return bytes(pdf)


def write_simple_pdf(path: Path, lines: list[str]) -> None:
    x = 72
    y = 750
    font_size = 12
    leading = 16

    stream_parts: list[str] = []
    for line in lines:
        esc = _pdf_escape(line)
        stream_parts.append(f"BT /F1 {font_size} Tf {x} {y} Td ({esc}) Tj ET\n")
        y -= leading
        if y < 72:
            break
    stream = "".join(stream_parts).encode("utf-8")
    path.write_bytes(_build_pdf(stream))


def write_table_pdf(path: Path, rows: list[tuple[str, str]]) -> None:
    left_metric = 72
    left_value = 430
    top = 700
    row_h = 46

    stream_parts: list[str] = []
    stream_parts.append("BT /F1 28 Tf 72 750 Td (Index Analytics) Tj ET\n")

    header_y = top - 20
    stream_parts.append(f"BT /F1 16 Tf {left_metric} {header_y} Td (Metric) Tj ET\n")
    stream_parts.append(f"BT /F1 16 Tf {left_value} {header_y} Td (Value) Tj ET\n")

    for i, (metric, value) in enumerate(rows):
        y = top - ((i + 1) * row_h) - 20
        m = _pdf_escape(metric)
        v = _pdf_escape(value)
        stream_parts.append(f"BT /F1 14 Tf {left_metric} {y} Td ({m}) Tj ET\n")
        stream_parts.append(f"BT /F1 14 Tf {left_value} {y} Td ({v}) Tj ET\n")

    stream = "".join(stream_parts).encode("utf-8")
    path.write_bytes(_build_pdf(stream))


def main() -> None:
    p = argparse.ArgumentParser(prog="ics_search_engine.report")
    p.add_argument("--index", required=True)
    p.add_argument("--out", default="")
    args = p.parse_args()

    index_dir = Path(args.index)
    stats_path = index_dir / "stats.json"
    stats = json.loads(stats_path.read_text(encoding="utf-8"))

    md = render_markdown(stats)
    out = args.out.strip()
    if out:
        out_path = Path(out)
        if out_path.suffix.lower() == ".pdf":
            rows = [
                ("Indexed documents", str(int(stats.get("indexed_documents", 0)))),
                ("Unique tokens", str(int(stats.get("unique_tokens", 0)))),
                ("Index size on disk (KB)", f"{float(stats.get('core_index_kb', 0.0)):.2f}"),
            ]
            write_table_pdf(out_path, rows)
        else:
            out_path.write_text(md, encoding="utf-8")
        return

    (index_dir / "report.md").write_text(md, encoding="utf-8")
    rows = [
        ("Indexed documents", str(int(stats.get("indexed_documents", 0)))),
        ("Unique tokens", str(int(stats.get("unique_tokens", 0)))),
        ("Index size on disk (KB)", f"{float(stats.get('core_index_kb', 0.0)):.2f}"),
    ]
    write_table_pdf(index_dir / "report.pdf", rows)


if __name__ == "__main__":
    main()
