[byterover-mcp]

# important

always use byterover-retrieve-knowledge tool to get the related context before any tasks

always use byterover-store-knowledge to store all the critical informations after sucessful tasks

---

# Project Rules: html_parse_sync Node

These guidelines standardize future contributions and automated agent modifications.

## Scope

- Node performs **pure HTML parsing only**. No network / HTTP requests.
- Keep dependency footprint to Python standard library.

## Style & Structure

- Expose adjustable parameters via `INPUT_TYPES` (add optional inputs instead of hardcoding when reasonable).
- Use ALL_CAPS constants for tunables (e.g., `DEFAULT_MAX_CHARS`).
- Keep helper functions file-local (no global state beyond constants & mappings).
- Prefer regex heuristics; avoid heavy parsers unless a compelling accuracy need emerges.

## Safety & Robustness

- Never raise uncaught exceptions during `run`; fallback to empty strings or `"unknown"`.
- Sanitize numeric inputs (bounds check & type cast) before use.
- Strip potentially unsafe script/style/comment content early (`_strip_blocks`).

## Performance

- Avoid repeated large-regex scans; reuse compiled patterns where hot (see `_CANDIDATES`).
- Soft cap content length before expensive downstream nodes.

## Extensibility

- When adding new extraction fields, also append them to:
  - RETURN_TYPES / RETURN_NAMES
  - JSON output serialization
  - README documentation
- Keep README changelog current with semantic bump.

## Testing (Manual Quick Check)

```python
from custom_nodes.html_parse_sync import HTMLParseSync
sample_html = "<html><head><title>X</title></head><body><article><h1>H</h1><p>Body</p></article></body></html>"
print(HTMLParseSync().run(sample_html, "https://example.com/x")[0])
```

## Versioning

- Patch: internal refactor / doc / minor heuristic tune
- Minor: new optional input or extraction field
- Major: behavior changes that alter existing outputs or defaults

---

End of rules.
