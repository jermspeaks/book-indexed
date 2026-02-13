"""
Map index refs to chapters and sort by order of appearance (first occurrence per term).
Unified logic for EPUB (file -> chapter) and PDF (page -> chapter).
"""
from typing import Any


def _page_display(start: int, end: int) -> str:
    """Format page as '120' or '120-125' for display."""
    return str(start) if start == end else f"{start}-{end}"


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
    Map each index ref (file_basename, start, end) to chapter using file_to_chapter.
    Sort by (chapter_order, start page). One entry per term (first appearance).
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

    # Explode: (term, subentry, refs) -> list of (term, subentry, chapter, start, order, subheading, page_display)
    rows: list[tuple[str, str, str, int, int, str, str]] = []
    for item in index_entries:
        term = (item.get("term") or "").strip()
        subentry = (item.get("subentry") or "").strip()
        refs = item.get("refs") or []
        for ref in refs:
            if len(ref) == 2:
                file_basename, page = ref
                start, end = page, page
            else:
                file_basename, start, end = ref[0], ref[1], ref[2]
            if not file_basename:
                continue
            chapter = file_to_chapter.get(file_basename, "Other")
            order = basename_to_order.get(file_basename, 9999)
            subheading = _subheading_for_ref(
                file_basename, start, subheading_by_file_and_page
            )
            page_display = _page_display(start, end)
            rows.append((term, subentry, chapter, start, order, subheading, page_display))

    return _first_appearance_by_chapter(rows)


def map_and_sort_pdf(
    toc: list[dict[str, Any]],
    index_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Map each index ref (None, start, end) to chapter using TOC page ranges.
    Sort by (chapter_order, start page). One entry per term (first appearance).
    Returns list of {chapter_name, entries: [{term, subentry, page}, ...]} in chapter order.
    """
    rows: list[tuple[str, str, str, int, int, str, str]] = []
    for item in index_entries:
        term = (item.get("term") or "").strip()
        subentry = (item.get("subentry") or "").strip()
        refs = item.get("refs") or []
        for ref in refs:
            if len(ref) == 2:
                _f, page = ref
                start, end = page, page
            else:
                _f, start, end = ref[0], ref[1], ref[2]
            chapter = "Other"
            order = 9999
            for i, ch in enumerate(toc):
                ch_start = ch.get("start_page", 0)
                ch_end = ch.get("end_page", 0)
                if ch_start <= start <= ch_end:
                    chapter = ch.get("name", "Other")
                    order = i
                    break
            page_display = _page_display(start, end)
            rows.append((term, subentry, chapter, start, order, "", page_display))

    return _first_appearance_by_chapter(rows)


def _first_appearance_by_chapter(
    rows: list[tuple[str, str, str, int, int, str, str]],
) -> list[dict[str, Any]]:
    """
    rows = (term, subentry, chapter, start_page, chapter_order, subheading, page_display).
    Sort by (chapter_order, start_page). Keep first occurrence per (term, subentry).
    Group by chapter; within chapter sort by start_page. Entry page is display string ("120" or "120-125").
    """
    if not rows:
        return []

    # Sort by chapter_order then start_page, then (term, subentry) for stability
    rows_sorted = sorted(rows, key=lambda r: (r[4], r[3], r[0], r[1]))

    # First appearance per (term, subentry)
    seen: set[tuple[str, str]] = set()
    first_occurrences: list[tuple[str, str, str, int, str, str]] = []
    for term, subentry, chapter, start_page, _, subheading, page_display in rows_sorted:
        key = (term, subentry)
        if key in seen:
            continue
        seen.add(key)
        first_occurrences.append((term, subentry, chapter, start_page, subheading, page_display))

    # Group by chapter (preserve order of first occurrence)
    chapter_order: list[str] = []
    chapter_entries: dict[str, list[dict[str, Any]]] = {}
    for term, subentry, chapter, start_page, subheading, page_display in first_occurrences:
        if chapter not in chapter_order:
            chapter_order.append(chapter)
        if chapter not in chapter_entries:
            chapter_entries[chapter] = []
        chapter_entries[chapter].append({
            "term": term,
            "subentry": subentry,
            "page": page_display,
            "subheading": subheading,
            "_sort_page": start_page,
        })

    # Sort entries within each chapter by start_page, then drop sort key
    for ch in chapter_entries:
        chapter_entries[ch].sort(key=lambda e: (e["_sort_page"], e["term"], e["subentry"]))
        for e in chapter_entries[ch]:
            del e["_sort_page"]

    return [
        {"chapter_name": ch, "entries": chapter_entries[ch]}
        for ch in chapter_order
        if ch in chapter_entries
    ]
