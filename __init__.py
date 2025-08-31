# html_parse_sync/__init__.py
# ------------------------------------------------------------
# HTML Parse (sync) — extracts title/author/content + domain/site
# Inputs :
#   - html (STRING, required) : full page HTML
#   - url  (STRING, optional) : original page URL (for domain/site)
# Outputs (STRING):
#   - json, title, content, author, domain, site_name
# ------------------------------------------------------------

import re
import json as _json
from datetime import datetime
from html import unescape as _unescape
from urllib.parse import urlparse

__version__ = "0.1.3"

# Default maximum characters retained for extracted content (can be overridden per run)
DEFAULT_MAX_CHARS = 8000

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# ---------- helpers ----------
def _discover_url(html: str, passed: str) -> str:
    """Best-effort discovery of canonical/source URL.

    Tries (in order): explicit passed URL, <link rel=canonical>, og:url meta, <base href>.
    Regexes are made order-agnostic regarding attribute ordering.
    """
    if passed:
        return passed
    # Two patterns to allow rel/href order variance
    m1 = re.search(r'<link[^>]*?rel=["\']canonical["\'][^>]*?href=["\']([^"\']+)["\']', html, re.I)
    if not m1:
        m1 = re.search(r'<link[^>]*?href=["\']([^"\']+)["\'][^>]*?rel=["\']canonical["\']', html, re.I)
    if m1:
        return m1.group(1)
    m2 = re.search(r'<meta[^>]+property=["\']og:url["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
    if m2:
        return m2.group(1)
    m3 = re.search(r'<base[^>]*href=["\']([^"\']+)["\']', html, re.I)
    if m3:
        return m3.group(1)
    return ""

def _extract_domain_site(u: str):
    try:
        host = urlparse(u).hostname or ""
        if host.startswith("www."):
            host = host[4:]
        exts = [
            ".co.uk",".com.au",".co.za",".co.in",".co.jp",".co.kr",
            ".com",".net",".org",".edu",".gov",".mil",".int",
            ".info",".biz",".name",".pro",".museum",".coop",
            ".uk",".de",".fr",".it",".es",".nl",".be",".ch",".at",
            ".se",".no",".dk",".fi",".pl",".cz",".hu",
            ".io",".ai",".ly",".me",".tv",".cc",".ws",".blog",
        ]
        exts.sort(key=len, reverse=True)
        site = host
        for ext in exts:
            if site.endswith(ext):
                site = site[: -len(ext)]
                break
        return host or "unknown", site or "unknown"
    except Exception:
        m = re.search(r'https?://(?:www\.)?([^/]+)', u or "")
        if m:
            host = m.group(1)
            site = re.sub(r'(\.co\.uk|\.com\.au|\.com|\.net|\.org)$', "", host, flags=re.I)
            return host, site
        return "unknown", "unknown"

_BLOCK_TAGS = r"(nav|header|footer|aside|iframe|noscript|template)"

def _strip_blocks(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.I)
    html = re.sub(r"<!--[\s\S]*?-->", "", html)
    html = re.sub(rf"<{_BLOCK_TAGS}[\s\S]*?</{_BLOCK_TAGS}>", "", html, flags=re.I)
    html = re.sub(
        r'<[^>]+class=["\'][^"\']*(comment|comments|sidebar|advert|ads|ad-|promo|newsletter|cookie|consent|subscribe)[^"\']*["\'][^>]*>[\s\S]*?</[^>]+>',
        "", html, flags=re.I
    )
    return html

_CANDIDATES = [
    re.compile(r"<article[^>]*>([\s\S]*?)</article>", re.I),
    re.compile(r"<main[^>]*>([\s\S]*?)</main>", re.I),
    re.compile(r'<div[^>]+class=["\'][^"\']*(post-content|entry-content|article-content|content-area|post-body|content)[^"\']*["\'][^>]*>([\s\S]*?)</div>', re.I),
]

def _pick_section(html: str) -> str:
    best = ""
    for rx in _CANDIDATES:
        m = rx.search(html)
        if m:
            payload = (m.group(1) if m.lastindex and m.lastindex >= 1 else "") or \
                      (m.group(2) if m.lastindex and m.lastindex >= 2 else "")
            if len(re.sub(r"\s+", " ", payload)) > len(re.sub(r"\s+", " ", best)):
                best = payload
    if not best:
        m = re.search(r"<body[^>]*>([\s\S]*?)</body>", html, re.I)
        best = (m and m.group(1)) or html
    return best

def _clean(s: str) -> str:
    """Remove HTML tags, unescape entities, normalize whitespace."""
    text = re.sub(r"<[^>]*>", "", s or "")
    text = _unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _extract_title(html: str) -> str:
    h1 = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html, re.I)
    if h1: return _clean(h1.group(1))
    og = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
    if og: return _clean(og.group(1))
    tt = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, re.I)
    if tt: return _clean(tt.group(1))
    alt = re.search(r'<(h1|h2)[^>]*class=["\'][^"\']*(post-title|entry-title|article-title)[^"\']*["\'][^>]*>([\s\S]*?)</\1>', html, re.I)
    if alt: return _clean(alt.group(3))
    return ""

def _extract_author(html: str) -> str:
    meta = re.search(r'<meta[^>]+name=["\']author["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
    if meta: return _clean(meta.group(1))
    inline = re.search(r'<(?:span|div)[^>]+class=["\'][^"\']*(author|byline|post-author)[^"\']*["\'][^>]*>([\s\S]*?)</(?:span|div)>', html, re.I)
    if inline: return _clean(inline.group(2))
    rel = re.search(r'<a[^>]+rel=["\']author["\'][^>]*>([\s\S]*?)</a>', html, re.I)
    if rel: return _clean(rel.group(1))
    return ""

def _html_to_text(snippet: str) -> str:
    s = snippet
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)

    def repl_block(m: re.Match) -> str:
        close, tag = m.group(1), m.group(2)
        return "\n" if close or re.match(r"h[1-4]$", tag, re.I) else ""

    s = re.sub(r"<(/?)(p|div|section|article|li|ul|ol|h1|h2|h3|h4|blockquote)[^>]*>", repl_block, s, flags=re.I)
    s = re.sub(r"<li[^>]*>", "• ", s, flags=re.I)

    def table_to_text(m: re.Match) -> str:
        t = m.group(0)
        t = re.sub(r"<tr[^>]*>", "\n", t, flags=re.I)
        t = re.sub(r"</tr>", "\n", t, flags=re.I)
        t = re.sub(r"<t[dh][^>]*>", " ", t, flags=re.I)
        t = re.sub(r"</t[dh]>", " ", t, flags=re.I)
        t = re.sub(r"<[^>]+>", "", t)
        return t

    s = re.sub(r"<table[\s\S]*?</table>", table_to_text, s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("\r", "")
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = _unescape(s).strip()
    return s

def _cap_chars(s: str, n: int | None) -> str:
    if not s:
        return ""
    if n is None:
        n = DEFAULT_MAX_CHARS
    if n and n > 0 and len(s) > n:
        return s[:n] + "..."
    return s

def _cap_wordsafe(s: str, n: int | None) -> str:
    if not s:
        return ""
    if n is None:
        n = DEFAULT_MAX_CHARS
    if not (n and n > 0) or len(s) <= n:
        return s
    # Find last whitespace before limit - 1 to leave space for ellipsis
    cut = s.rfind(" ", 0, max(0, n - 1))
    if cut == -1 or cut < n * 0.5:  # fallback if no good breakpoint
        cut = n
    truncated = s[:cut].rstrip()
    return truncated + " …"

def _word_count(s: str) -> int:
    return len([w for w in (s or "").strip().split() if w])

# ---------- node ----------
class HTMLParseSync:
    """Parse already-fetched HTML (no network) and extract article-style metadata.

    Inputs:
      - html (STRING, required): Raw HTML markup.
      - url  (STRING, optional): Original page URL (improves domain/site extraction).
      - max_chars (INT, optional): Cap length of cleaned content (default 8000).

    Outputs (all STRING): json, title, content, author, domain, site_name.
    Design goals: zero external deps, resilient to malformed HTML, heuristic-based.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"html": ("STRING", {"default": ""})},
            "optional": {
                "url": ("STRING", {"default": ""}),
                "max_chars": ("INT", {"default": DEFAULT_MAX_CHARS, "min": 500, "max": 50000, "step": 500}),
                "word_safe": ("BOOLEAN", {"default": True, "label": "Word-safe truncation"}),
                "prompt_template": ("STRING", {"default": "", "multiline": True, "placeholder": "e.g. Summarize the article titled '{title}' from {domain}:\n\n{content}"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("json", "title", "content", "author", "domain", "site_name", "word_count", "prompt")
    FUNCTION = "run"
    CATEGORY = "Text/Parsing"

    def run(self, html: str, url: str = "", max_chars: int = DEFAULT_MAX_CHARS, word_safe: bool = True, prompt_template: str = ""):
        raw_html = html or ""
        discovered_url = _discover_url(raw_html, url or "")
        domain, site_name = _extract_domain_site(discovered_url)

        cleaned = _strip_blocks(raw_html)
        section = _pick_section(cleaned)
        title = _extract_title(cleaned)
        author = _extract_author(cleaned)
        content = _html_to_text(section)

        # Sanitize and clamp max_chars (avoid absurd values while allowing override)
        try:
            max_chars_int = int(max_chars)
        except Exception:
            max_chars_int = DEFAULT_MAX_CHARS
        if max_chars_int < 0:
            # disable capping
            pass
        else:
            max_chars_int = max(100, min(max_chars_int, 100_000))
            content = (_cap_wordsafe if word_safe else _cap_chars)(content, max_chars_int)
        wc = _word_count(content)

        # Build placeholder context
        content_snip = (_cap_wordsafe if word_safe else _cap_chars)(content, 1000)
        placeholders = {
            "url": discovered_url or "unknown",
            "domain": domain,
            "site_name": site_name,
            "title": title,
            "content": content,
            "content_snip": content_snip,
            "author": author,
            "word_count": wc,
            "version": __version__,
            "extracted_at": datetime.utcnow().isoformat() + "Z",
        }

        class _Safe(dict):
            def __missing__(self, key):
                # Leave unknown placeholder visibly unaltered
                return '{' + key + '}'

        formatted_prompt = ""
        if prompt_template:
            try:
                formatted_prompt = prompt_template.format_map(_Safe(placeholders))
            except Exception:
                # Fallback: basic replacement using curly braces tokens
                formatted_prompt = prompt_template
                for k, v in placeholders.items():
                    formatted_prompt = formatted_prompt.replace('{' + k + '}', str(v))

        out = {**placeholders}
        json_blob = _json.dumps(out, ensure_ascii=False)

        return (
            json_blob,
            title or "",
            content or "",
            author or "",
            domain or "",
            site_name or "",
            str(wc),
            formatted_prompt or "",
        )

NODE_CLASS_MAPPINGS["HTMLParseSync"] = HTMLParseSync
NODE_DISPLAY_NAME_MAPPINGS["HTMLParseSync"] = "HTML Parse (sync)"
