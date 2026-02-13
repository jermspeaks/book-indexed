# Book Analyzer

Re-organize a book’s index by **order of appearance** per chapter and export it as Markdown. Supports **EPUB** and **PDF** inputs.

## What it does

- **EPUB**: Reads the built-in table of contents and index from the EPUB, maps each index term to its chapter, and lists terms in the order they first appear in each chapter.
- **PDF**: You specify TOC and index page ranges; raw text is extracted and structured with an LLM (Gemini or OpenAI), then index terms are mapped to chapters and sorted by first appearance.

Output is a single Markdown file (e.g. `output/The Art of Gathering_index.md`) with the book title, then one section per chapter containing index entries in reading order.

## Requirements

- Python 3.10+
- See [requirements.txt](requirements.txt) for dependencies.

**PDF path only:** You need an API key for structuring the index and TOC:

- **Gemini** (recommended): `GEMINI_API_KEY` or `GOOGLE_API_KEY` from [Google AI Studio](https://aistudio.google.com/)
- **OpenAI** (optional): `OPENAI_API_KEY` if you prefer GPT-4o-mini

## Setup

```bash
git clone <repo>
cd book-analyzer
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

For PDF support, copy the example env and add your key:

```bash
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=... or OPENAI_API_KEY=...
```

## Usage

### EPUB

No API key needed. Run:

```bash
python main.py path/to/book.epub
```

Output goes to `output/` by default. Example:

```bash
python main.py example.epub -o output
```

### PDF

You must pass the **index page range**; the TOC range is optional (default `5-8`).

```bash
python main.py path/to/book.pdf --index-pages 450-470
```

With custom TOC and output directory:

```bash
python main.py book.pdf --toc-pages 3-10 --index-pages 450-470 -o output
```

| Option | Description | Default |
|--------|-------------|--------|
| `input_path` | Path to EPUB or PDF | (required) |
| `-o`, `--output-dir` | Output directory | `output` |
| `--toc-pages` | PDF: TOC page range (START-END) | `5-8` |
| `--index-pages` | PDF: index page range (START-END) | (required for PDF) |

## Output

The script writes a single file: `output/<BookTitle>_index.md`.

Structure:

- **Title** (e.g. `# The Art of Gathering`)
- **Index (by order of appearance)** — one `### Chapter Name` section per chapter
- Under each chapter: index entries as `- **Term** (subentry) — p. N`, in the order the term first appears in that chapter.

Example snippet:

```markdown
# The Art of Gathering

## Index (by order of appearance)

### Introduction

- **Birthday parties** — p. 9
- **Board meetings** — p. 9
- **Connecting** (failed) — p. 10
...

### One | Decide Why You're Really Gathering

- **Decision making** — p. 1
- **Welcoming** — p. 1
...
```

## Project structure

```
book-analyzer/
├── main.py              # CLI entry point
├── requirements.txt
├── .env.example         # API key template for PDF
├── src/
│   ├── extract_epub.py  # EPUB: TOC + index extraction
│   ├── extract_pdf.py   # PDF: raw text from page ranges
│   ├── structure_index.py  # PDF: LLM structuring (Gemini/OpenAI)
│   ├── map_and_sort.py # Map index terms to chapters, sort by first appearance
│   └── export_md.py     # Write grouped index to Markdown
└── output/              # Generated *_index.md files (default)
```

## License

Listed in LICENSE.md, using MIT

