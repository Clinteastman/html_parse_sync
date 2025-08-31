# HTML Parse (sync) — ComfyUI Custom Node

Extract clean article metadata (title, author, content, domain, site name + JSON blob) from raw HTML inside a ComfyUI workflow **without making network requests**.

> Fast, dependency‑light (only stdlib: `re`, `json`, `datetime`, `html`, `urllib`), and intentionally heuristic. Ideal for lightweight content ingestion, prototyping RAG pipelines, or feeding LLM prompts.

---

## Features

- Strips scripts, styles, comments, nav/aside/footer/header/iframes/templates and common ad / promo / cookie / newsletter blocks.
- Attempts to locate the _main content_ via `<article>`, `<main>`, or common content class names; falls back to `<body>`.
- Extracts:
  - `title` (from `<h1>`, OpenGraph, `<title>`, or known title classes)
  - `author` (meta name=author, byline/author class spans/divs, rel=author links)
  - `content` (normalized plaintext; lists → bullets, tables → text)
  - `domain` + `site_name` (derived from provided or discovered URL)
  - `word_count` (separate output + JSON)
  - `version` metadata + timestamp
- Word-safe truncation option (prevents mid-word cuts) with configurable max length.
- Unicode preserved (`ensure_ascii=False`).

---

## Installation

Place (or clone) this folder into your ComfyUI `custom_nodes/` directory:

```text
ComfyUI/
  custom_nodes/
    html_parse_sync/
      __init__.py
      README.md
```

Restart ComfyUI. The node will appear under: `Text / Parsing` as **HTML Parse (sync)**.

No extra Python packages required.

---

## Node Specification

**Class**: `HTMLParseSync`

### Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| html | STRING | Yes | Raw HTML content of the page. |
| url  | STRING | No  | Original page URL (used for domain + site heuristics; can be blank). |
| max_chars | INT | No | Max content characters (capped, word-safe by default). |
| word_safe | BOOLEAN | No | If true, truncation ends at a word boundary. |
| prompt_template | STRING | No | Optional prompt template with placeholders (see below). |

If `url` is blank, the node will try to discover a canonical/og/base URL inside the HTML.

### Outputs (all STRING)

| Position | Name | Description |
|----------|------|-------------|
| 1 | json | JSON string with all extracted fields. |
| 2 | title | Extracted title (may be empty). |
| 3 | content | Cleaned article plaintext (capped). |
| 4 | author | Author/byline (may be empty). |
| 5 | domain | e.g., `example.com`. |
| 6 | site_name | Heuristic site identifier (root minus public suffix). |
| 7 | word_count | Word count (stringified integer). |
| 8 | prompt | Rendered prompt if a template was provided (else empty). |

### JSON Structure

Example `json` output field (pretty printed here for clarity):

```json
{
  "url": "https://example.com/post/123",
  "domain": "example.com",
  "site_name": "example",
  "title": "An Example Article",
  "content": "First paragraph...\n\nSecond paragraph...",
  "author": "Jane Doe",
  "word_count": 173,
  "version": "0.1.3",
  "extracted_at": "2025-08-31T12:34:56.789012Z"
}
```

### Prompt Templating

If you provide a `prompt_template`, the node renders it and outputs the result as the final `prompt` output.

Placeholders (use Python `{name}` style):

| Placeholder | Meaning |
|-------------|---------|
| `{title}` | Extracted title |
| `{author}` | Extracted author/byline |
| `{content}` | Full (possibly truncated) cleaned content |
| `{content_snip}` | ~1000 char word-safe snippet of content |
| `{domain}` | Domain (e.g., example.com) |
| `{site_name}` | Site name heuristic |
| `{url}` | Discovered or provided URL |
| `{word_count}` | Integer word count |
| `{version}` | Node version |
| `{extracted_at}` | ISO UTC timestamp |

Unknown placeholders are left unchanged (`{unknown_placeholder}`) so you can spot typos easily.

Example template:

```text
Summarize the article below. Title: {title}\nDomain: {domain}\nWords: {word_count}\n\n{content_snip}\n\nReturn a JSON summary.
```

Note: If you need a literal brace, escape with double braces `{{` or `}}`.

---

## Usage Example (Conceptual)

1. Use a node (or external process) to fetch HTML (e.g., via a separate HTTP fetch custom node or preloaded string).
2. Connect the HTML string to `html` input.
3. (Optional) Provide URL.
4. Feed `content` or `json` to downstream LLM / embedding / summarization nodes.

### Minimal Test (outside ComfyUI)

```python
from custom_nodes.html_parse_sync import HTMLParseSync
html = """<html><head><title>Test</title><meta name=author content='Alex'></head>\n<body><article><h1>Sample Heading</h1><p>Hello <b>world</b>.</p></article></body></html>"""
node = HTMLParseSync()
json_out, title, content, author, domain, site, wc = node.run(html, "https://example.org/test")
print(title, author, domain, site, wc)
print(content)
print(json_out)
```

---

## Heuristics & Notes

- Main section detection favors first matching candidate with the **largest normalized text length** among `<article>`, `<main>`, and content-class `<div>`.
- Author extraction is best‑effort; pages with unusual markup may return empty.
- `site_name` is derived by shaving a recognized public suffix (simplistic list). Edge TLDs not in the list may produce longer `site_name` strings.
- Content bullets: `<li>` → `•`. Tables flattened to spaced cell text with row breaks.
- Excessive whitespace collapsed; multiple blank lines reduced to a max of two.
- Hard length cap ensures predictable token usage (default 8000, adjustable; <0 disables; word boundary safe by default).

---

## Limitations / Non‑Goals

- No JavaScript execution (dynamic / lazy-loaded content will be absent).
- No full boilerplate readability scoring (e.g., arc90/Readability). Simple regex heuristics only.
- Not a sanitizer against malicious HTML—intended for already trusted/fetched content.
- International domain / complex public suffix parsing is minimal (does not integrate with the Public Suffix List library).

---

## Extending

Common tweak points inside `__init__.py`:

- `_BLOCK_TAGS` — add/remove container tags to drop.
- `_CANDIDATES` — expand regex list for main content detection.
- `_cap_wordsafe` / `_cap_chars` — adjust truncation behavior.
- `_extract_author` / `_extract_title` — add more patterns.
- `_strip_blocks` — extend class substring filters (ads, cookie notices, etc.).

All helpers are file‑local; feel free to convert to a more modular structure if complexity grows.

---

## Error Handling

The node avoids raising exceptions for malformed input; unexpected parsing errors fall back to safe defaults (`""` or `"unknown"`).

---

## Changelog

### 0.1.3

- Added prompt templating system with new `prompt_template` input and `prompt` output.
- Added `content_snip` placeholder.
- Version bump.

### 0.1.2

- Added `word_count` as separate output.
- Added semantic `version` field in JSON.
- Added word-safe truncation option (`word_safe`).
- Improved canonical URL attribute-order handling.
- `_clean` now HTML-unescapes entities before normalization.

### 0.1.1

- Fixed use of non‑existent Python `str.trim()` (now uses standardized whitespace normalization + `strip()`).

### 0.1.0

- Initial release.

---

## Roadmap Ideas

- Optional readability scoring.
- Language detection for downstream model routing.
- Optional markdown formatting (e.g., heading reconstruction).
- Public Suffix List integration for better `site_name` derivation.

---

## License

Choose and add a license file (e.g., MIT) if you plan to distribute. (Currently unspecified.)

---

## Feedback

PRs and suggestions welcome. If you extend heuristics for specific publishers, consider contributing patterns back.
