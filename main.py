#!/usr/bin/env python3
"""
Book index re-organizer: extract TOC and index from EPUB or PDF,
map index terms to chapters by order of appearance, output master index as Markdown.
"""
import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-organize book index by order of appearance per chapter; output Markdown to output/."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Path to EPUB or PDF file",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Output directory (default: output)",
    )
    parser.add_argument(
        "--toc-pages",
        type=str,
        metavar="START-END",
        default="5-8",
        help="PDF only: TOC page range, e.g. 5-8 (default: 5-8)",
    )
    parser.add_argument(
        "--index-pages",
        type=str,
        metavar="START-END",
        default="",
        help="PDF only: index page range, e.g. 450-470 (required for PDF)",
    )
    args = parser.parse_args()

    path = args.input_path.resolve()
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".epub":
        run_epub(path, args.output_dir)
    elif suffix == ".pdf":
        run_pdf(path, args.output_dir, args.toc_pages, args.index_pages)
    else:
        raise SystemExit("Input must be an .epub or .pdf file.")


def run_epub(epub_path: Path, output_dir: Path) -> None:
    from src.extract_epub import extract_epub
    from src.map_and_sort import map_and_sort_epub
    from src.export_md import export_markdown

    print("Extracting TOC and index from EPUB...")
    data = extract_epub(epub_path)
    print(f"  Book: {data['book_title']}")
    print(f"  TOC entries: {len(data['toc'])}, index entries: {len(data['index_entries'])}")

    print("Mapping index to chapters and sorting by order of appearance...")
    grouped = map_and_sort_epub(
        data["toc"],
        data["spine_hrefs"],
        data["file_to_chapter"],
        data["index_entries"],
    )

    out_path = export_markdown(data["book_title"], grouped, output_dir)
    print(f"Wrote: {out_path}")


def run_pdf(
    pdf_path: Path,
    output_dir: Path,
    toc_pages_str: str,
    index_pages_str: str,
) -> None:
    from src.extract_pdf import extract_pdf
    from src.structure_index import structure_index_with_llm, structure_toc_with_llm
    from src.map_and_sort import map_and_sort_pdf
    from src.export_md import export_markdown

    def parse_range(s: str) -> tuple[int, int]:
        parts = s.strip().split("-")
        if len(parts) != 2:
            raise SystemExit(f"Invalid page range: {s}. Use START-END, e.g. 5-8")
        try:
            return int(parts[0].strip()), int(parts[1].strip())
        except ValueError:
            raise SystemExit(f"Invalid page range: {s}")

    if not index_pages_str:
        raise SystemExit("PDF requires --index-pages START-END (e.g. --index-pages 450-470)")

    toc_start, toc_end = parse_range(toc_pages_str)
    index_start, index_end = parse_range(index_pages_str)

    print("Extracting TOC and index pages from PDF...")
    raw = extract_pdf(pdf_path, toc_start, toc_end, index_start, index_end)
    print(f"  TOC raw length: {len(raw['toc_raw'])}, index raw length: {len(raw['index_raw'])}")

    print("Structuring index with LLM...")
    index_entries = structure_index_with_llm(raw["index_raw"])
    print("Structuring TOC with LLM...")
    toc = structure_toc_with_llm(raw["toc_raw"], last_page=raw["page_count"])

    print("Mapping index to chapters and sorting by order of appearance...")
    grouped = map_and_sort_pdf(toc, index_entries)

    book_title = pdf_path.stem.replace("_", " ").replace("-", " ")
    out_path = export_markdown(book_title, grouped, output_dir)
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
