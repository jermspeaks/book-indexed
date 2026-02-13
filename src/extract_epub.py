"""
Extract TOC and index from an EPUB file.
Uses toc.ncx (or nav), content.opf spine, and Index.xhtml parsing.
"""
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Any

from bs4 import BeautifulSoup


# Roman numeral to int for common front-matter pages (i, ii, iii, iv, v, vi, vii, viii, ix, x, xi, xii, xiii, xiv, ...)
ROMAN_TO_INT = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8,
    "ix": 9, "x": 10, "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15,
    "xvi": 16, "xvii": 17, "xviii": 18, "xix": 19, "xx": 20,
}


def _normalize_page(page_str: str) -> int:
    """Convert page string (numeric or roman) to int for sorting."""
    page_str = page_str.strip().lower()
    if page_str in ROMAN_TO_INT:
        return ROMAN_TO_INT[page_str]
    try:
        return int(re.sub(r"[^\d]", "", page_str) or "0") or 0
    except ValueError:
        return 0


def _get_opf_path(epub_path: str | Path) -> str:
    """Read META-INF/container.xml to get path to content.opf."""
    with zipfile.ZipFile(epub_path, "r") as z:
        with z.open("META-INF/container.xml") as f:
            tree = ET.parse(f)
            root = tree.getroot()
            # Default namespace
            ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
            elem = root.find(".//c:rootfile[@media-type='application/oebps-package+xml']", ns)
            if elem is not None and elem.get("full-path"):
                return elem.get("full-path")
            elem = root.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
            if elem is not None and elem.get("full-path"):
                return elem.get("full-path")
    return "content.opf"


def _parse_ncx(epub_path: str | Path, opf_path: str) -> list[dict[str, Any]]:
    """Parse toc.ncx and return list of {title, href} for each navPoint (first occurrence per file)."""
    opf_dir = str(Path(opf_path).parent)
    ncx_path = None
    with zipfile.ZipFile(epub_path, "r") as z:
        for name in z.namelist():
            if name.endswith("toc.ncx"):
                ncx_path = name
                break
    if not ncx_path:
        return []

    with zipfile.ZipFile(epub_path, "r") as z:
        with z.open(ncx_path) as f:
            tree = ET.parse(f)
            root = tree.getroot()

    def local(tag: str | None) -> str:
        if tag is None:
            return ""
        return tag.split("}")[-1] if "}" in tag else tag

    def find_text(el: ET.Element) -> str:
        for c in el.iter():
            if local(c.tag) == "text" and (c.text or "").strip():
                return (c.text or "").strip()
        return ""

    seen_hrefs: set[str] = set()
    toc: list[dict[str, Any]] = []
    for np in root.iter():
        if local(np.tag) != "navPoint":
            continue
        content_el = None
        label_el = None
        for child in np:
            if local(child.tag) == "content":
                content_el = child
            if local(child.tag) == "navLabel":
                label_el = child
        if content_el is None:
            continue
        src = (content_el.get("src") or "").strip()
        if not src:
            continue
        href_no_frag = src.split("#")[0]
        base = Path(href_no_frag).name
        if base in seen_hrefs:
            continue
        seen_hrefs.add(base)
        title = find_text(label_el) if label_el is not None else ""
        toc.append({"title": title, "href": href_no_frag, "file_basename": base})
    return toc


def _parse_opf_manifest_spine(epub_path: str | Path, opf_path: str) -> tuple[dict[str, str], list[str]]:
    """Return (id -> href map, ordered list of hrefs from spine)."""
    with zipfile.ZipFile(epub_path, "r") as z:
        with z.open(opf_path) as f:
            tree = ET.parse(f)
            root = tree.getroot()
    ns = {"opf": "http://www.idpf.org/2007/opf"}
    manifest: dict[str, str] = {}
    for item in root.findall(".//{http://www.idpf.org/2007/opf}item"):
        item_id = item.get("id")
        href = item.get("href")
        if item_id and href:
            manifest[item_id] = href
    spine_order: list[str] = []
    for itemref in root.findall(".//{http://www.idpf.org/2007/opf}itemref"):
        idref = itemref.get("idref")
        if idref and idref in manifest:
            spine_order.append(manifest[idref])
    return manifest, spine_order


def _find_index_href(epub_path: str | Path, opf_path: str, manifest: dict[str, str]) -> str | None:
    """Find href of the index document (epub:type=index or filename *Index*.xhtml)."""
    opf_dir = str(Path(opf_path).parent)
    for href in manifest.values():
        if "index" in href.lower() and href.endswith((".xhtml", ".html")):
            return href
    return None


def _parse_chapter_subheadings(
    epub_path: str | Path, opf_path: str, chapter_href: str
) -> list[tuple[int, str]]:
    """
    Parse a chapter XHTML and return a sorted list of (page_int, subheading_str).
    Each tuple means "at this page, this subheading applies (until the next recorded page)."
    Subheadings are taken from <h2> and <h3>; page boundaries from elements with id="page_N".
    """
    opf_dir = Path(opf_path).parent
    chapter_path = (opf_dir / chapter_href).as_posix().replace("//", "/")
    with zipfile.ZipFile(epub_path, "r") as z:
        try:
            raw = z.read(chapter_path)
        except KeyError:
            basename = chapter_href.split("/")[-1]
            for name in z.namelist():
                if name.endswith(basename):
                    raw = z.read(name)
                    break
            else:
                return []
    soup = BeautifulSoup(raw, "lxml")
    current_subheading = ""
    last_recorded: str | None = None
    result: list[tuple[int, str]] = []
    for tag in soup.find_all(True):
        if tag.name in ("h2", "h3"):
            current_subheading = (tag.get_text(separator=" ", strip=True) or "").strip()
        elif tag.get("id"):
            page_match = re.search(r"page[_\-]?(\w+)", tag.get("id", ""), re.I)
            if page_match:
                page_int = _normalize_page(page_match.group(1))
                if last_recorded != current_subheading:
                    result.append((page_int, current_subheading))
                    last_recorded = current_subheading
    return sorted(result, key=lambda x: x[0])


def _parse_index_html(epub_path: str | Path, index_href: str, opf_path: str) -> list[dict[str, Any]]:
    """Parse Index.xhtml and return list of {term, subentry, refs: [(file_basename, page_int)]}."""
    opf_dir = Path(opf_path).parent
    # Resolve index path relative to opf
    index_path = (opf_dir / index_href).as_posix().replace("//", "/")
    with zipfile.ZipFile(epub_path, "r") as z:
        try:
            raw = z.read(index_path)
        except KeyError:
            # Try without leading path
            for name in z.namelist():
                if name.endswith(index_href.split("/")[-1]) and "index" in name.lower():
                    raw = z.read(name)
                    break
            else:
                return []

    soup = BeautifulSoup(raw, "lxml")
    # Find all index entry paragraphs (Index-1, Index-2, Index-Alpha; exclude Index-Note, Index-Head)
    entries: list[dict[str, Any]] = []
    current_main_term: str = ""

    for p in soup.find_all("p", class_=re.compile(r"Index-(1|2|Alpha)", re.I)):
        if not p.get("class"):
            continue
        classes = " ".join(p.get("class", []))
        if "Index-Note" in classes or "Index-Head" in classes:
            continue

        # Extract refs: <a href="...xhtml#page_N"> or #page_N
        refs: list[tuple[str, int]] = []
        for a in p.find_all("a", href=True):
            href = a.get("href", "")
            if "#page_" not in href and "#page" not in href.lower():
                continue
            parts = href.split("#", 1)
            if len(parts) != 2:
                continue
            path_part, frag = parts
            file_basename = Path(path_part).name if path_part else ""
            if not file_basename:
                continue
            # Fragment: page_143 or page_xii or page_295
            page_match = re.search(r"page[_\-]?(\w+)", frag, re.I)
            if page_match:
                page_str = page_match.group(1)
                refs.append((file_basename, _normalize_page(page_str)))

        # Term and subentry: use text before first <a> (page refs) to avoid page numbers in term
        def text_before_first_link(tag) -> str:
            parts: list[str] = []
            for c in tag.children:
                if getattr(c, "name", None) == "a":
                    break
                if isinstance(c, str):
                    parts.append(c)
                elif hasattr(c, "get_text"):
                    parts.append(c.get_text(separator=" ", strip=True))
            return "".join(parts).strip().strip(",").strip()

        raw_text = text_before_first_link(p)
        # "see also" / "see" entries have no refs - skip or keep with empty refs (skip for mapping)
        if "Index-2" in classes or "index-2" in classes:
            subentry = raw_text
            term = current_main_term
        else:
            term = raw_text
            subentry = ""
            current_main_term = term

        # Skip pure "see" cross-refs if no refs (optional: could keep for display)
        if not refs and ("see" in raw_text.lower() or "continued" in raw_text.lower()):
            continue
        entries.append({"term": term, "subentry": subentry, "refs": refs})
    return entries


def extract_epub(epub_path: str | Path) -> dict[str, Any]:
    """
    Extract TOC and index from an EPUB.
    Returns:
        book_title: str (from docTitle in NCX or dc:title in OPF)
        toc: list of {title, href, file_basename} in nav order
        spine_hrefs: list of hrefs in reading order
        index_entries: list of {term, subentry, refs: [(file_basename, page_int)]}
        file_to_chapter: dict file_basename -> chapter title (from toc)
        subheading_by_file_and_page: dict file_basename -> [(page_int, subheading_str), ...]
    """
    epub_path = Path(epub_path)
    if not epub_path.exists():
        raise FileNotFoundError(f"EPUB not found: {epub_path}")

    opf_path = _get_opf_path(epub_path)
    manifest, spine_hrefs = _parse_opf_manifest_spine(epub_path, opf_path)
    toc = _parse_ncx(epub_path, opf_path)
    file_to_chapter: dict[str, str] = {e["file_basename"]: e["title"] for e in toc}

    # Book title from OPF (dc:title) or NCX (docTitle)
    book_title = ""
    with zipfile.ZipFile(epub_path, "r") as z:
        with z.open(opf_path) as f:
            tree = ET.parse(f)
            root = tree.getroot()
            for t in root.iter():
                if t.tag is not None and "title" in t.tag.lower() and (t.text or "").strip():
                    book_title = (t.text or "").strip()
                    break
    if not book_title and toc:
        ncx_path = next((n for n in zipfile.ZipFile(epub_path, "r").namelist() if n.endswith("toc.ncx")), None)
        if ncx_path:
            with zipfile.ZipFile(epub_path, "r") as z:
                with z.open(ncx_path) as f:
                    ncx = ET.parse(f)
                    for t in ncx.getroot().iter():
                        if t.tag is not None and "docTitle" in t.tag and len(t) > 0:
                            for c in t:
                                if c.tag is not None and "text" in c.tag and (c.text or "").strip():
                                    book_title = (c.text or "").strip()
                                    break
                            break
    if not book_title:
        book_title = epub_path.stem

    index_href = _find_index_href(epub_path, opf_path, manifest)
    index_entries: list[dict[str, Any]] = []
    if index_href:
        index_entries = _parse_index_html(epub_path, index_href, opf_path)

    subheading_by_file_and_page: dict[str, list[tuple[int, str]]] = {}
    for toc_entry in toc:
        href = toc_entry.get("href", "")
        file_basename = toc_entry.get("file_basename") or Path(href).name
        if not href:
            continue
        subheading_by_file_and_page[file_basename] = _parse_chapter_subheadings(
            epub_path, opf_path, href
        )

    return {
        "book_title": book_title,
        "toc": toc,
        "spine_hrefs": spine_hrefs,
        "index_entries": index_entries,
        "file_to_chapter": file_to_chapter,
        "subheading_by_file_and_page": subheading_by_file_and_page,
    }
