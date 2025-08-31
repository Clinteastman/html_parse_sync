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

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# ---------- helpers ----------
def _discover_url(html: str, passed: str) -> str:
    if passed:
        return passed
    m1 = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html, re.I)
    if m1: return m1.group(1)
    m2 = re.search(r'<meta[^>]+property=["\']og:url["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
    if m2: return m2.group(1)
    m3 = re.search(r'<base[^>]*href=["\']([^"\']+)["\']', html, re.I)
    if m3: return m3.group(1)
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
    """Remove HTML tags and trim/normalize whitespace.

    Python's str does not have a trim() method (that's from JS); previous
    version attempted a hasattr(str, 'trim') guard which is unnecessary and
    could confuse linters. We always use strip() and also collapse internal
    whitespace to a single space for cleaner output.
    """
    text = re.sub(r"<[^>]*>", "", s or "")
    # Collapse runs of whitespace (including newlines) to a single space
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

def _cap(s: str, n: int = 8000) -> str:
    return (s[:n] + "...") if s and len(s) > n else (s or "")

def _word_count(s: str) -> int:
    return len([w for w in (s or "").strip().split() if w])

# ---------- node ----------
class HTMLParseSync:
    """
    Parse HTML (no network), extract title/author/content + domain/site_name.
    Inputs:
      - html (STRING)
      - url  (STRING, optional)
    Outputs:
      - json, title, content, author, domain, site_name (all STRING)
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": { "html": ("STRING", {"default": ""}) },
            "optional": { "url":  ("STRING", {"default": ""}) },
        }

    RETURN_TYPES = ("STRING","STRING","STRING","STRING","STRING","STRING")
    RETURN_NAMES = ("json","title","content","author","domain","site_name")
    FUNCTION = "run"
    CATEGORY = "Text/Parsing"

    def run(self, html: str, url: str = ""):
        raw_html = html or ""
        discovered_url = _discover_url(raw_html, url or "")
        domain, site_name = _extract_domain_site(discovered_url)

        cleaned = _strip_blocks(raw_html)
        section = _pick_section(cleaned)
        title   = _extract_title(cleaned)
        author  = _extract_author(cleaned)
        content = _html_to_text(section)
        content = _cap(content, 8000)
        wc = _word_count(content)

        out = {
            "url": discovered_url or "unknown",
            "domain": domain,
            "site_name": site_name,
            "title": title,
            "content": content,
            "author": author,
            "word_count": wc,
            "extracted_at": datetime.utcnow().isoformat() + "Z",
        }

        return (_json.dumps(out, ensure_ascii=False),
                title or "",
                content or "",
                author or "",
                domain or "",
                site_name or "")

NODE_CLASS_MAPPINGS["HTMLParseSync"] = HTMLParseSync
NODE_DISPLAY_NAME_MAPPINGS["HTMLParseSync"] = "HTML Parse (sync)"
