"""
Build and write the master index as Markdown to output/<book>_index.md.
"""
from pathlib import Path
from typing import Any


def export_markdown(
    book_title: str,
    grouped: list[dict[str, Any]],
    output_dir: str | Path,
    output_filename: str | None = None,
) -> Path:
    """
    Write master index to output_dir / (output_filename or <book_title>_index.md).
    Returns path to written file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if output_filename is None:
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in book_title).strip("_")
        output_filename = f"{safe_title}_index.md"
    out_path = output_dir / output_filename

    lines: list[str] = []
    lines.append(f"# {book_title}")
    lines.append("")
    lines.append("## Index (by order of appearance)")
    lines.append("")

    for section in grouped:
        chapter_name = section.get("chapter_name", "Other")
        entries = section.get("entries", [])
        lines.append(f"### {chapter_name}")
        lines.append("")
        for e in entries:
            term = e.get("term", "")
            subentry = e.get("subentry", "")
            page = e.get("page", "")
            if subentry:
                lines.append(f"- **{term}** ({subentry}) — p. {page}")
            else:
                lines.append(f"- **{term}** — p. {page}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
