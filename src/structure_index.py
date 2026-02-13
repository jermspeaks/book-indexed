"""
Structure raw index text into JSON using an LLM (for PDF path).
Also optional: structure TOC raw text into chapter name + page ranges.
"""
import json
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

INDEX_STRUCTURE_PROMPT = """You will receive raw text from a book index. Convert it into a JSON list of objects.
Each object must have: "term" (string), "subentry" (string, optional, use "" if none), and "pages" (list of integers).
For page ranges like "120-125" or "120–125", include only the first number in the list (e.g. 120).
Roman numerals (ix, xi, xii) should be converted to integers (9, 11, 12).
Skip "see also" and "see" cross-reference lines that have no page numbers.
Return only valid JSON, no markdown or explanation.

Raw index text:

{index_raw}
"""

TOC_STRUCTURE_PROMPT = """You will receive raw text from a book's table of contents. Convert it into a JSON list of objects.
Each object must have: "name" (chapter/section title), "start_page" (integer), "end_page" (integer).
Infer end_page as the start_page of the next chapter minus 1, or use the last page of the book for the last chapter.
Roman numerals (ix, xi, etc.) should be converted to integers.
Return only valid JSON, no markdown or explanation.

Raw TOC text:

{toc_raw}
"""


def _call_gemini(prompt: str, max_tokens: int = 16000) -> str:
    """Call Gemini API (Google GenAI SDK) and return generated text."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError(
            "google-genai package required for Gemini. pip install google-genai"
        )
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY not set in environment or .env")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=max_tokens),
    )
    return (response.text or "").strip()


def _call_openai(prompt: str, max_tokens: int = 16000) -> str:
    """Call OpenAI API and return assistant content."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package required for PDF index structuring. pip install openai")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment or .env")
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()


def _call_llm(prompt: str, max_tokens: int = 16000) -> str:
    """Call configured LLM (Gemini or OpenAI) and return response text."""
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return _call_gemini(prompt, max_tokens=max_tokens)
    if os.environ.get("OPENAI_API_KEY"):
        return _call_openai(prompt, max_tokens=max_tokens)
    raise ValueError(
        "Set GEMINI_API_KEY, GOOGLE_API_KEY, or OPENAI_API_KEY in .env for PDF index structuring."
    )


def _extract_json_from_response(text: str) -> list[dict[str, Any]]:
    """Extract JSON array from LLM response (handle markdown code blocks)."""
    text = text.strip()
    # Remove markdown code block if present
    if "```" in text:
        for part in text.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                try:
                    return json.loads(part)
                except json.JSONDecodeError:
                    continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find [...] substring
    start = text.find("[")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    return []


def structure_index_with_llm(index_raw: str) -> list[dict[str, Any]]:
    """
    Send raw index text to LLM and return list of {term, subentry, pages}.
    """
    prompt = INDEX_STRUCTURE_PROMPT.format(index_raw=index_raw[:50000])
    response = _call_llm(prompt)
    data = _extract_json_from_response(response)
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        term = item.get("term") or item.get("title") or ""
        subentry = item.get("subentry") or ""
        pages = item.get("pages") or item.get("page") or []
        if isinstance(pages, int):
            pages = [pages]
        pages = [int(p) for p in pages if p is not None]
        if term:
            out.append({"term": str(term).strip(), "subentry": str(subentry).strip(), "refs": [(None, p) for p in pages]})
    return out


def structure_toc_with_llm(toc_raw: str, last_page: int = 500) -> list[dict[str, Any]]:
    """
    Send raw TOC text to LLM and return list of {name, start_page, end_page}.
    """
    if not toc_raw.strip():
        return []
    prompt = TOC_STRUCTURE_PROMPT.format(toc_raw=toc_raw[:8000])
    response = _call_llm(prompt, max_tokens=4000)
    data = _extract_json_from_response(response)
    out = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("title") or ""
        start = item.get("start_page") or item.get("start") or 0
        end = item.get("end_page") or item.get("end")
        if end is None and i + 1 < len(data):
            next_item = data[i + 1]
            if isinstance(next_item, dict):
                end = (next_item.get("start_page") or next_item.get("start") or start + 1) - 1
        if end is None:
            end = last_page
        out.append({"name": str(name).strip(), "start_page": int(start), "end_page": int(end)})
    return out
