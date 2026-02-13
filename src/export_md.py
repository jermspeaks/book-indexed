"""
Build and write the master index as Markdown to output/<book>_index.md.
"""
from pathlib import Path
from typing import Any


def _display_label(term: str, subentry: str) -> str:
    """Format index label: 'Subentry term' when subentry present (title-cased), else term."""
    if not subentry:
        return term
    sub = subentry.strip()
    if sub:
        sub = sub[0].upper() + sub[1:]
    return f"{sub} {term}".strip()


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
        # Group entries by subheading (empty first, then first-appearance order)
        subheading_order: list[str] = []
        subheading_to_entries: dict[str, list[dict[str, Any]]] = {}
        for e in entries:
            subheading = e.get("subheading") or ""
            if subheading not in subheading_to_entries:
                subheading_order.append(subheading)
                subheading_to_entries[subheading] = []
            subheading_to_entries[subheading].append(e)
        for subheading in subheading_order:
            group_entries = subheading_to_entries[subheading]
            if subheading:
                lines.append(f"#### {subheading}")
                lines.append("")
            for e in group_entries:
                term = e.get("term", "")
                subentry = e.get("subentry", "")
                page = e.get("page", "")
                label = _display_label(term, subentry)
                lines.append(f"- **{label}** — p. {page}")
            lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
