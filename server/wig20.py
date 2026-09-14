"""
WIG20 index constituents management.

Queries the current list of WIG20 companies from an LLM (OpenAI-compatible
API), caches the result on disk, and refreshes it on a daily schedule. If the
LLM or the network is unavailable, it falls back to a hardcoded last-known
list so the table always renders something.

Configuration is driven by environment variables (used as defaults) and can be
overridden at runtime from the Settings page (in-memory, per-process):

    LLM_API_KEY   API key (required for the LLM lookup).
    LLM_PROVIDER  Provider key selecting the OpenAI-compatible base URL.
                  - openai:   https://api.openai.com/v1
                  - deepseek: https://api.deepseek.com/v1
                  - zai:      https://api.z.ai/api/paas/v4
    LLM_MODEL     Model name. Defaults to the first model of the provider.
    LLM_USE_WEB_SEARCH  "1"/"true" to ground the lookup in live web results
                  via the OpenAI Responses API web search tool. Defaults to
                  enabled; it only applies to the OpenAI endpoint and falls
                  back to a plain chat call otherwise.
    WIG20_REFRESH_ON_START  "1"/"true" to perform an immediate warm-up refresh
                  when the scheduler starts. The scheduler also refreshes on
                  start if the cache is missing or stale (last refreshed on an
                  earlier day). Defaults to disabled so server restarts during
                  development do not trigger an LLM call.
"""
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta

import requests
from urllib.parse import urlparse

# --- Fallback (last known) WIG20 constituents --------------------------------
DEFAULT_WIG20_TICKERS = [
    'CDR.WA', 'PKN.WA', 'PKO.WA', 'PZU.WA', 'MBK.WA',
    'SPL.WA', 'PEO.WA', 'KGH.WA', 'LPP.WA', 'PGE.WA',
    'ALR.WA', 'DNP.WA', 'ALE.WA', 'ZAB.WA', 'CCC.WA',
    'KTY.WA', 'KRU.WA', 'PCO.WA', 'OPL.WA', 'BDX.WA',
]

# --- Configuration (overridable via environment variables) ------------------
LLM_API_KEY = os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

# LLM providers offered in the Settings page. Each is OpenAI-compatible and
# pins the base URL to the selected provider, so picking a provider in the UI
# automatically selects the right endpoint.
LLM_PROVIDERS = {
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": [ "gpt-4o", "gpt-5-mini", "gpt-5", "gpt-5.4-nano", "gpt-5.4-mini", "gpt-5.4"],
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-flash", "deepseek-v4-pro"],
    },
    "zai": {
        "label": "Z.ai",
        "base_url": "https://api.z.ai/api/paas/v4",
        "models": ["glm-4.7-plus", "glm-5", "glm-5.1", "glm-5.2", "glm-5.3-flash", "glm-5.3"],
    },
}

# Environment defaults, used until the Settings page overrides them.
_ENV_PROVIDER = os.environ.get("LLM_PROVIDER", "DeepSeek")
_ENV_MODEL = os.environ.get("LLM_MODEL", "deepseek-flash")

# Runtime overrides set via the Settings page (in-memory "python variables").
# When None, the environment defaults above are used.
_selected_provider = None
_selected_model = None
_selected_api_key = None

LLM_USE_WEB_SEARCH = os.environ.get("LLM_USE_WEB_SEARCH", "1").lower() in ("1", "true", "yes")


def get_llm_provider():
    """Return the selected LLM provider key (runtime override or env default)."""
    return _selected_provider or _ENV_PROVIDER


def get_llm_model():
    """Return the selected model (runtime override, env default, or provider default)."""
    if _selected_model:
        return _selected_model
    if _ENV_MODEL:
        return _ENV_MODEL
    return LLM_PROVIDERS[get_llm_provider()]["models"][0]


def get_llm_base_url():
    """Return the OpenAI-compatible base URL for the selected provider."""
    return LLM_PROVIDERS[get_llm_provider()]["base_url"]


def set_llm_settings(provider, model):
    """Override the LLM provider/model selected in the Settings page.

    Raises ``ValueError`` for an unknown provider or a model not offered by it.
    """
    global _selected_provider, _selected_model
    if provider not in LLM_PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {provider!r}")
    if model not in LLM_PROVIDERS[provider]["models"]:
        raise ValueError(f"Unknown model {model!r} for provider {provider!r}")
    _selected_provider = provider
    _selected_model = model


def get_llm_api_key():
    """Return the API key (runtime override, or the environment default)."""
    return _selected_api_key or LLM_API_KEY


def set_llm_api_key(api_key):
    """Override the LLM API key selected in the Settings page.

    An empty/blank value clears the override, falling back to ``LLM_API_KEY``.
    """
    global _selected_api_key
    _selected_api_key = (api_key or "").strip() or None
# When enabled, the scheduler performs an immediate warm-up refresh on startup.
# Disabled by default so a server restart (common during development) does not
# trigger an LLM call; set it to "1"/"true" when iterating on this area. Even
# when disabled, the scheduler still refreshes if the cache is missing/stale.
WIG20_REFRESH_ON_START = os.environ.get("WIG20_REFRESH_ON_START", "0").lower() in ("1", "true", "yes")
WIG20_CACHE_FILE = os.environ.get("WIG20_CACHE_FILE", "cache/wig20_constituents.json")
DIAGNOSTICS_LOG_FILE = os.environ.get("WIG20_DIAGNOSTICS_LOG", "cache/wig20_diagnostics.jsonl")

_refresh_lock = threading.Lock()

# Guards against starting more than one scheduler thread per process (e.g. if
# start_wig20_scheduler() is invoked more than once during startup).
_scheduler_thread = None
_scheduler_start_lock = threading.Lock()

# Domains the web-search tool routinely returns that are not authoritative for
# WIG20 constituents (social media, forums, blogspam, unrelated PDFs, mirrors,
# and near-duplicate technical-analysis pages). Filtered out of the stored
# "visited URLs" list so diagnostics stay readable. This is intentionally
# conservative and only drops clear noise - it never removes the "cited" set.
_URL_DENYLIST = {
    "reddit.com",
    "linkedin.com",
    "substack.com",
    "researchgate.net",
    "opensanctions.org",
    "eticanews.it",
    "cne.cl",
    "muslimxchange.com",
    "ayondo.com",
    "naga.com",
    "stockinvest.us",
    "buysidedigest.com",
    "compoundwithrene.com",
    "robertditrych.substack.com",
    "koomberg.pl",
    "prudo.pl",
    "fin-reports.pl",
    "stocktoria.com",
    "topforeignstocks.com",
    "databahn.com",
    "marketgenius.app",
    "modivoplatform.com",
    "freenance.io",
    "rt.http3.lol",
    "dspace.cuni.cz",
    "bip.uek.krakow.pl",
}


class Wig20Diagnostics:
    """Collects status/diagnostics from a single WIG20 lookup.

    The same structure is printed to the log, stored in the cache on success,
    and appended to a pretty-printed JSON log file, so per-model statistics can
    be built later.
    """

    def __init__(self, model):
        self.model = model
        self.requested_at = datetime.now()  # when this lookup started
        self.source = None           # "web_search" | "chat"
        self.visited_urls = []       # filtered/deduped search sources (see below)
        self.cited_urls = []         # URLs actually cited in the final answer
        self.json_ok = None          # None (no LLM call) / True / False
        self.json_error = None
        self.raw_tickers = []
        self.repeated_tickers = []
        self.format_issues = []
        self.ticker_count = 0
        self.errors = []
        self.warnings = []

    def add_error(self, msg):
        self.errors.append(str(msg))

    def add_warning(self, msg):
        self.warnings.append(str(msg))

    def to_dict(self):
        return {
            "requested_at": self.requested_at.isoformat(timespec="seconds"),
            "model": self.model,
            "source": self.source,
            "visited_urls": list(self.visited_urls),
            "cited_urls": list(self.cited_urls),
            "json_ok": self.json_ok,
            "json_error": self.json_error,
            "raw_count": len(self.raw_tickers),
            "repeated_tickers": list(self.repeated_tickers),
            "format_issues": list(self.format_issues),
            "ticker_count": self.ticker_count,
            "count_mismatch": self.ticker_count != 20,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }

    def summarize(self, with_details=False):
        lines = [
            f"[wig20] diagnostics: model={self.model} source={self.source} "
            f"requested_at={self.requested_at.isoformat(timespec='seconds')}"
        ]

        lines.append(
            f"  urls: visited={len(self.visited_urls)} cited={len(self.cited_urls)}"
        )
        if self.visited_urls and with_details:
            lines.append("  visited URLs:")
            for u in self.visited_urls:
                lines.append(f"    - {u}")
        if self.cited_urls and with_details:
            lines.append("  cited URLs:")
            for u in self.cited_urls:
                lines.append(f"    - {u}")
        
        lines.append(
            f"  json_ok={self.json_ok}" + (f" ({self.json_error})" if self.json_error else "")
        )
        lines.append(f"  raw={len(self.raw_tickers)} repeated={self.repeated_tickers or 'none'}")
        if self.format_issues:
            lines.append(f"  format_issues ({len(self.format_issues)}):")
            for fi in self.format_issues:
                lines.append(f"    - {fi['raw']!r} -> {fi['normalized']!r}")
        lines.append(f"  normalized={self.ticker_count} count_ok={self.ticker_count == 20}")
        for w in self.warnings:
            lines.append(f"  WARNING: {w}")
        for e in self.errors:
            lines.append(f"  ERROR: {e}")
        return "\n".join(lines)


def _log_diagnostics(diag):
    """Append one diagnostics record as pretty-printed JSON to the log file.

    Each record is written with indentation and newlines for human readability,
    separated from the next by a blank line. The file is append-only and is
    intended for manual inspection and later statistics.
    """
    try:
        os.makedirs(os.path.dirname(DIAGNOSTICS_LOG_FILE) or ".", exist_ok=True)
        with open(DIAGNOSTICS_LOG_FILE, "a") as f:
            f.write(json.dumps(diag.to_dict(), indent=2) + "\n\n")
    except OSError as e:
        print(f"[wig20] could not write diagnostics log: {e}")


def _load_cache():
    """Return the cached payload or None if missing/corrupt."""
    try:
        with open(WIG20_CACHE_FILE, "r") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save_cache(payload):
    os.makedirs(os.path.dirname(WIG20_CACHE_FILE) or ".", exist_ok=True)
    with open(WIG20_CACHE_FILE, "w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def _parse_tickers(content):
    """Extract a list of ticker strings from an LLM text response."""
    content = (content or "").strip()

    print(f"[wig20] LLM response: {content[:400]}{'...' if len(content) > 400 else ''}")
    # Strip markdown code fences, e.g. ```json [...] ```.
    if content.startswith("```"):
        content = content.strip("`").strip()
        if content.lower().startswith("json"):
            content = content[4:].strip()

    # If the model wrapped the array in prose, extract the first JSON array.
    match = re.search(r"\[.*\]", content, re.DOTALL)
    if not match:
        if not content:
            raise ValueError(
                "LLM returned an empty response (no content to parse as JSON)"
            )
        raise ValueError(
            f"LLM response contained no JSON array: {content[:120]!r}"
        )
    content = match.group(0)

    tickers = json.loads(content)
    if not isinstance(tickers, list) or not tickers:
        raise ValueError("LLM returned an invalid ticker list")

    return [str(t).strip().upper() for t in tickers if str(t).strip()]


# Common ticker-name mistakes: map a wrong/verbose token to the real GPW code.
TICKER_ALIASES = {
    "ORLEN": "PKN",
    "PKNORLEN": "PKN",
    "SANTANDER": "SPL",
    "ERSTE": "EBP",
    "PEKAO": "PEO",
    "BANKPEKAO": "PEO",
    "KGHM": "KGH",
    "ALLEGRO": "ALE",
    "CDPROJEKT": "CDR",
    "CDPROJEKTRED": "CDR",
    "MBANK": "MBK",
    "ZABKA": "ZAB",
    "ALIOR": "ALR",
    "ALIORBANK": "ALR",
    "KETY": "KTY",
    "GRUPAKETY": "KTY",
    "TAURON": "TPE",
    "BUDIMEX": "BDX",
    "KRUK": "KRU",
    "PEPCO": "PCO",
    "PKOBP": "PKO",
    "DNIPOLSKA": "DNP",
}

_TICKER_CODE_RE = re.compile(r"[A-Z0-9]{3,4}")


def _normalize_one(value):
    """Normalize a single raw entry into a Yahoo .WA ticker, or None."""
    t = str(value).strip().upper()
    if not t:
        return None
    if t.endswith(".WA"):
        t = t[:-3]
    # Extract the first all-caps alphanumeric token as the candidate code.
    m = re.search(r"[A-Z0-9]+", t)
    if not m:
        return None
    code = TICKER_ALIASES.get(m.group(0), m.group(0))
    if not _TICKER_CODE_RE.fullmatch(code):
        return None
    return f"{code}.WA"


def _normalize_tickers(tickers):
    """Normalize raw LLM output into valid Yahoo .WA tickers, fixing aliases."""
    result = []
    seen = set()
    for raw in tickers:
        yahoo = _normalize_one(raw)
        if yahoo and yahoo not in seen:
            seen.add(yahoo)
            result.append(yahoo)
    return result


def _is_clean_ticker(value):
    """True if the entry already looks like a proper ticker code (3-4 A-Z0-9)."""
    t = str(value).strip().upper()
    if t.endswith(".WA"):
        t = t[:-3]
    return bool(_TICKER_CODE_RE.fullmatch(t))


_PROMPT = (
    "Find the CURRENT list of the 20 companies in the WIG20 index (Warsaw "
    "Stock Exchange, GPW) as of today. Return ONLY a valid JSON array of their "
    "Yahoo Finance ticker symbols, each ending in .WA, for example "
    '["PKO.WA", "PKN.WA"]. '
    "Use the official GPW ticker for each company; the ticker is not always "
    "the company name (e.g. Orlen is PKN.WA, PKO Bank Polski is PKO.WA, "
    "Pekao is PEO.WA, KGHM is KGH.WA, mBank is MBK.WA). Do not add commentary."
)


def _http_error(resp):
    """Build a descriptive error string including the response body.

    OpenAI-compatible APIs return a JSON body with an "error" object that
    explains why a request failed (e.g. unsupported model, bad parameter),
    which `requests`' HTTPError message omits. Including it makes 400-class
    errors diagnosable instead of a bare "Bad Request".
    """
    try:
        body = resp.text
    except Exception:
        body = "<no response body>"
    return f"{resp.status_code} {resp.reason} for {resp.url}\nResponse body: {body}"


def _query_chat(prompt):
    """Plain chat-completions call (no web search)."""
    url = f"{get_llm_base_url().rstrip('/')}/chat/completions"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {get_llm_api_key()}",
            "Content-Type": "application/json",
        },
        json={
            "model": get_llm_model(),
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(_http_error(resp))
    content = resp.json()["choices"][0]["message"]["content"]
    return content


def _extract_urls(data):
    """Collect URLs from an OpenAI Responses API result.

    Returns a tuple ``(cited, searched)`` of URL entry dicts::

        {"url": str, "title": str, "hostname": str}

    ``cited`` are the URLs actually cited in the assistant's final answer
    (message ``url_citation`` annotations) - the subset the model considered
    useful. ``searched`` are every source the web-search tool retrieved
    (``web_search_call.action.sources``) - the raw crawl list, which is far
    larger and mostly noise.
    """
    searched = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "web_search_call":
            for src in (item.get("action") or {}).get("sources", []) or []:
                if isinstance(src, dict) and src.get("url"):
                    searched.append(_source_entry(src))

    cited = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for block in item.get("content", []) or []:
                if not isinstance(block, dict):
                    continue
                for ann in block.get("annotations", []) or []:
                    if isinstance(ann, dict) and ann.get("url"):
                        cited.append(_source_entry(ann))

    return cited, searched


def _source_entry(src):
    """Normalize a web-search source/annotation dict into a URL entry."""
    url = src.get("url") or ""
    hostname = (src.get("hostname") or "").lower().lstrip("www.")
    if not hostname:
        hostname = urlparse(url).netloc.lower().lstrip("www.")
    return {"url": url, "title": src.get("title") or "", "hostname": hostname}


def _dedupe_by_hostname(entries):
    """Collapse URL entries to one per hostname, keeping the first occurrence."""
    seen, result = set(), []
    for e in entries:
        hostname = e.get("hostname")
        if hostname and hostname in seen:
            continue
        if hostname:
            seen.add(hostname)
        result.append(e)
    return result


def _filter_noise(entries, denylist):
    """Drop entries whose hostname is on the denylist."""
    return [e for e in entries if e.get("hostname") not in denylist]


def _query_with_web_search(prompt):
    """OpenAI Responses API with the web search tool. Returns (content, cited, searched)."""
    if "openai.com" not in get_llm_base_url():
        raise RuntimeError("Web search is only supported with the OpenAI endpoint.")
    url = f"{get_llm_base_url().rstrip('/')}/responses"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {get_llm_api_key()}",
            "Content-Type": "application/json",
        },
        json={
            "model": get_llm_model(),
            "input": prompt,
            "tools": [{"type": "web_search"}],            
            "tool_choice": {"type": "web_search"},
            "include": [
                "web_search_call.action.sources"
            ],
        },
        timeout=240,
    )
    if not resp.ok:
        raise RuntimeError(_http_error(resp))
    data = resp.json()
    cited, searched = _extract_urls(data)
    content = _extract_response_text(data)
    return content, cited, searched


def _extract_response_text(data):
    """Extract the assistant's text from an OpenAI Responses API payload."""
    if "output_text" in data:
        return data["output_text"]

    parts = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") in ("output_text", "text"):
                    parts.append(c.get("text", ""))
    return "".join(parts)


def query_wig20_via_llm(diag):
    """Populate `diag` and return the raw ticker list. Raises on hard failure."""
    if not get_llm_api_key():
        diag.add_error("No LLM API key configured")
        raise RuntimeError("No LLM API key configured (set LLM_API_KEY).")

    content = None
    if LLM_USE_WEB_SEARCH:
        try:
            content, cited, searched = _query_with_web_search(_PROMPT)
            diag.cited_urls = [e["url"] for e in cited]
            diag.visited_urls = [
                e["url"] for e in _filter_noise(_dedupe_by_hostname(searched), _URL_DENYLIST)
            ]
            diag.source = "web_search"
        except Exception as e:
            diag.add_warning(f"web search failed ({e}); falling back to plain LLM")

    if content is None:
        try:
            content = _query_chat(_PROMPT)
            diag.source = "chat"
        except Exception as e:
            diag.add_error(f"LLM request failed: {e}")
            raise

    try:
        tickers = _parse_tickers(content)
        diag.json_ok = True
    except Exception as e:
        diag.json_ok = False
        diag.json_error = str(e)
        diag.add_error(f"Incorrect JSON format: {e}")
        raise ValueError(f"incorrect JSON format: {e}") from e

    diag.raw_tickers = list(tickers)
    return tickers


def _analyze_raw_tickers(raw, diag):
    """Analyze raw tickers and normalize them, recording findings on `diag`.

    Returns the normalized ticker list (possibly empty).
    """
    diag.raw_tickers = list(raw)

    # Repeated tickers in the raw answer (before deduplication).
    counts = {}
    for t in raw:
        counts[t] = counts.get(t, 0) + 1
    diag.repeated_tickers = [t for t, c in counts.items() if c > 1]

    # Entries that were not clean tickers (e.g. company names) -> warnings.
    for entry in raw:
        if not _is_clean_ticker(entry):
            diag.format_issues.append({"raw": entry, "normalized": _normalize_one(entry)})

    normalized = _normalize_tickers(raw)
    diag.ticker_count = len(normalized)
    if normalized and diag.ticker_count != 20:
        diag.add_warning(f"not 20 tickers (got {diag.ticker_count})")

    if not normalized:
        diag.add_error("no valid tickers after normalization")

    return normalized


def refresh_wig20_tickers():
    """Re-query the LLM, analyze/normalize the result, and update the cache."""
    diag = Wig20Diagnostics(model=get_llm_model())
    try:
        raw = query_wig20_via_llm(diag)
    except Exception:
        _log_diagnostics(diag)
        print(diag.summarize())
        raise

    normalized = _analyze_raw_tickers(raw, diag)

    _save_cache({
        "tickers": normalized,
        "updated_at": time.time(),
        "diagnostics": diag.to_dict(),
    })
    _log_diagnostics(diag)
    print(diag.summarize())

    if not normalized:
        raise ValueError("no valid WIG20 tickers returned")
    return normalized


def _cache_is_stale():
    """Return True if the cache is missing/empty or was refreshed before today."""
    cached = _load_cache()
    if not cached or not cached.get("tickers"):
        return True
    updated_at = float(cached.get("updated_at", 0) or 0)
    last_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return updated_at < last_midnight.timestamp()


def get_wig20_tickers():
    """
    Return the current WIG20 ticker list (thread-safe).

    Reads the on-disk cache and falls back to the hardcoded last-known list if
    the cache is missing or empty. Refreshing is handled by the daily scheduler
    (see start_wig20_scheduler), not on the request path.
    """
    cached = _load_cache()
    if cached and cached.get("tickers"):
        return cached["tickers"]
    return list(DEFAULT_WIG20_TICKERS)


def _seconds_until_next_midnight():
    """Seconds from now until the next local midnight."""
    now = datetime.now()
    next_midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (next_midnight - now).total_seconds()


def start_wig20_scheduler():
    global _scheduler_thread
    """
    Start a daemon thread that refreshes WIG20 constituents daily at midnight.

    Also performs an immediate best-effort refresh so the cache is warm on
    first launch without blocking any request. That warm-up refresh runs when
    WIG20_REFRESH_ON_START is enabled, or when the cache is missing/stale (for
    example after the process was down over the last midnight). Disabled by
    default so that server restarts during development don't trigger an LLM
    call unless the cache is actually missing or from an earlier day.
    """
    def _run():
        # Initial warm-up refresh (best-effort, non-fatal). Runs when explicitly
        # enabled or when the cache is missing/stale.
        print(f"[wig20] scheduler thread started (refresh on start: {WIG20_REFRESH_ON_START})")
        if WIG20_REFRESH_ON_START or _cache_is_stale():
            try:
                with _refresh_lock:
                    refresh_wig20_tickers()
            except Exception as e:
                print(f"[wig20] initial refresh failed: {e}")

        while True:
            seconds = _seconds_until_next_midnight()
            time.sleep(seconds)
            print(f"[wig20] refreshing WIG20 tickers at {datetime.now().isoformat()} wait {seconds:.1f}s")
            try:
                with _refresh_lock:
                    refresh_wig20_tickers()
            except Exception as e:
                print(f"[wig20] scheduled refresh failed: {e}")

    with _scheduler_start_lock:
        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            print("[wig20] scheduler thread already running; skipping duplicate start")
            return _scheduler_thread
        thread = threading.Thread(target=_run, daemon=True, name="wig20-scheduler")
        _scheduler_thread = thread
        thread.start()
        return thread
