"""
Map index refs to chapters and sort by order of appearance (first occurrence per term).
Unified logic for EPUB (file -> chapter) and PDF (page -> chapter).
"""
from typing import Any


def _subheading_for_ref(
    file_basename: str,
    page: int,
    subheading_by_file_and_page: dict[str, list[tuple[int, str]]] | None,
) -> str:
    """Return the subheading for (file_basename, page) using the compressed list (last p <= page)."""
    if not subheading_by_file_and_page:
        return ""
    lst = subheading_by_file_and_page.get(file_basename) or []
    subheading = ""
    for p, s in lst:
        if p <= page:
            subheading = s
        else:
            break
    return subheading or ""


def map_and_sort_epub(
    toc: list[dict[str, Any]],
    spine_hrefs: list[str],
    file_to_chapter: dict[str, str],
    index_entries: list[dict[str, Any]],
    subheading_by_file_and_page: dict[str, list[tuple[int, str]]] | None = None,
) -> list[dict[str, Any]]:
    """
    Map each index ref (file_basename, page) to chapter using file_to_chapter.
    Sort by (chapter_order, page). One entry per term (first appearance).
    Returns list of {chapter_name, entries: [{term, subentry, page, subheading?}, ...]} in chapter order.
    """
    from pathlib import Path

    # Build spine order: href -> order index (by basename)
    href_to_basename = {h: Path(h).name for h in spine_hrefs}
    basename_to_order: dict[str, int] = {}
    for i, href in enumerate(spine_hrefs):
        base = href_to_basename.get(href) or Path(href).name
        if base not in basename_to_order:
            basename_to_order[base] = i

    # Explode: (term, subentry, refs) -> list of (term, subentry, chapter, page, chapter_order, subheading)
    rows: list[tuple[str, str, str, int, int, str]] = []
    for item in index_entries:
        term = (item.get("term") or "").strip()
        subentry = (item.get("subentry") or "").strip()
        refs = item.get("refs") or []
        for file_basename, page in refs:
            if not file_basename:
                continue
            chapter = file_to_chapter.get(file_basename, "Other")
            order = basename_to_order.get(file_basename, 9999)
            subheading = _subheading_for_ref(
                file_basename, page, subheading_by_file_and_page
            )
            rows.append((term, subentry, chapter, page, order, subheading))

    return _first_appearance_by_chapter(rows)


def map_and_sort_pdf(
    toc: list[dict[str, Any]],
    index_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Map each index ref (None, page) to chapter using TOC page ranges.
    Sort by (chapter_order, page). One entry per term (first appearance).
    Returns list of {chapter_name, entries: [{term, subentry, page}, ...]} in chapter order.
    """
    rows: list[tuple[str, str, str, int, int, str]] = []
    for item in index_entries:
        term = (item.get("term") or "").strip()
        subentry = (item.get("subentry") or "").strip()
        refs = item.get("refs") or []
        for _file_or_none, page in refs:
            chapter = "Other"
            order = 9999
            for i, ch in enumerate(toc):
                start = ch.get("start_page", 0)
                end = ch.get("end_page", 0)
                if start <= page <= end:
                    chapter = ch.get("name", "Other")
                    order = i
                    break
            rows.append((term, subentry, chapter, page, order, ""))

    return _first_appearance_by_chapter(rows)


def _first_appearance_by_chapter(
    rows: list[tuple[str, str, str, int, int, str]],
) -> list[dict[str, Any]]:
    """
    rows = (term, subentry, chapter, page, chapter_order, subheading).
    Sort by (chapter_order, page). Keep first occurrence per term (drop_duplicates on term).
    Group by chapter; within chapter sort by page. Each entry includes subheading when provided.
    """
    if not rows:
        return []

    # Sort by chapter_order then page
    rows_sorted = sorted(rows, key=lambda r: (r[4], r[3], r[0]))

    # First appearance per term (first occurrence wins)
    seen_terms: set[str] = set()
    first_occurrences: list[tuple[str, str, str, int, str]] = []
    for term, subentry, chapter, page, _, subheading in rows_sorted:
        if term in seen_terms:
            continue
        seen_terms.add(term)
        first_occurrences.append((term, subentry, chapter, page, subheading))

    # Group by chapter (preserve order of first occurrence)
    chapter_order: list[str] = []
    chapter_entries: dict[str, list[dict[str, Any]]] = {}
    for term, subentry, chapter, page, subheading in first_occurrences:
        if chapter not in chapter_order:
            chapter_order.append(chapter)
        if chapter not in chapter_entries:
            chapter_entries[chapter] = []
        chapter_entries[chapter].append({
            "term": term,
            "subentry": subentry,
            "page": page,
            "subheading": subheading,
        })

    # Sort entries within each chapter by page
    for ch in chapter_entries:
        chapter_entries[ch].sort(key=lambda e: (e["page"], e["term"]))

    return [
        {"chapter_name": ch, "entries": chapter_entries[ch]}
        for ch in chapter_order
        if ch in chapter_entries
    ]
