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
  - Full JSON bundle (pretty-ready string)
- Caps output content length (default 8000 chars) to avoid oversized downstream prompt payloads.
- Unicode preserved (`ensure_ascii=False`).

---
## Installation
Place (or clone) this folder into your ComfyUI `custom_nodes/` directory:
```
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
  "extracted_at": "2025-08-31T12:34:56.789012Z"
}
```

---
## Usage Example (Conceptual)
1. Use a node (or external process) to fetch HTML (e.g., via a separate HTTP fetch custom node or preloaded string).
2. Connect the HTML string to `html` input.
3. (Optional) Provide URL.
4. Feed `content` or `json` to downstream LLM / embedding / summarization nodes.

### Minimal Test (outside ComfyUI)
From a Python shell inside ComfyUI's environment:
```python
from custom_nodes.html_parse_sync import HTMLParseSync
html = """<html><head><title>Test</title><meta name=author content='Alex'></head>
<body><article><h1>Sample Heading</h1><p>Hello <b>world</b>.</p></article></body></html>"""
node = HTMLParseSync()
json_out, title, content, author, domain, site = node.run(html, "https://example.org/test")
print(title, author, domain, site)
print(content)
print(json_out)
```

---
## Heuristics & Notes
- Main section detection favors first matching candidate with the **largest normalized text length** among `<article>`, `<main>`, and content-class `<div>`.
- Author extraction is best‑effort; pages with unusual markup may return empty.
- `site_name` is derived by shaving a recognized public suffix (simplistic list). Edge TLDs not in the list may produce longer `site_name` strings.
- Content bullets: `<li>` → `• `. Tables flattened to spaced cell text with row breaks.
- Excessive whitespace collapsed; multiple blank lines reduced to a max of two.
- Hard length cap (8000 chars) ensures predictable token usage. Adjust in `_cap` if needed.

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
- `_cap` — change or disable length cap.
- `_extract_author` / `_extract_title` — add more patterns.
- `_strip_blocks` — extend class substring filters (ads, cookie notices, etc.).

All helpers are file‑local; feel free to convert to a more modular structure if complexity grows.

---
## Error Handling
The node avoids raising exceptions for malformed input; unexpected parsing errors fall back to safe defaults (`""` or `"unknown"`).

---
## Changelog
### 0.1.1
- Fixed use of non‑existent Python `str.trim()` (now uses standardized whitespace normalization + `strip()`).

### 0.1.0
- Initial release.

---
## Roadmap Ideas
- Optional readability scoring.
- Language detection for downstream model routing.
- Configurable max length via input parameter.
- Optional markdown formatting (e.g., heading reconstruction).
- Public Suffix List integration for better `site_name` derivation.

---
## License
Choose and add a license file (e.g., MIT) if you plan to distribute. (Currently unspecified.)

---
## Feedback
PRs and suggestions welcome. If you extend heuristics for specific publishers, consider contributing patterns back.
