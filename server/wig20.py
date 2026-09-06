"""
WIG20 index constituents management.

Queries the current list of WIG20 companies from an LLM (OpenAI-compatible
API), caches the result on disk, and refreshes it on a daily schedule. If the
LLM or the network is unavailable, it falls back to a hardcoded last-known
list so the table always renders something.

Configuration is driven by environment variables so the provider can be
switched without code changes:

    LLM_API_KEY   API key (required for the LLM lookup).
    LLM_BASE_URL  OpenAI-compatible base URL. Defaults to OpenAI.
                  - OpenAI:  https://api.openai.com/v1
                  - DeepSeek: https://api.deepseek.com/v1
                  - Qwen:    https://dashscope.aliyuncs.com/compatible-mode/v1
    LLM_MODEL     Model name. Defaults to "gpt-4o-mini".
                  - DeepSeek: "deepseek-chat", Qwen: "qwen-plus".
"""
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta

import requests

# --- Fallback (last known) WIG20 constituents --------------------------------
DEFAULT_WIG20_TICKERS = [
    'CDR.WA', 'PKN.WA', 'PKO.WA', 'PZU.WA', 'MBK.WA',
    'SPL.WA', 'PEO.WA', 'KGH.WA', 'LPP.WA', 'PGE.WA',
    'ALR.WA', 'DNP.WA', 'ALE.WA', 'ZAB.WA', 'CCC.WA',
    'KTY.WA', 'KRU.WA', 'PCO.WA', 'OPL.WA', 'BDX.WA',
]

# --- Configuration (overridable via environment variables) ------------------
LLM_API_KEY = os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
WIG20_CACHE_FILE = os.environ.get("WIG20_CACHE_FILE", "cache/wig20_constituents.json")

# Re-query at most once per day unless forced.
MAX_CACHE_AGE_SECONDS = 24 * 60 * 60

_refresh_lock = threading.Lock()


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
        json.dump(payload, f)


def _parse_tickers(content):
    """Extract a list of ticker strings from an LLM text response."""
    content = (content or "").strip()

    # Strip markdown code fences, e.g. ```json [...] ```.
    if content.startswith("```"):
        content = content.strip("`").strip()
        if content.lower().startswith("json"):
            content = content[4:].strip()

    # If the model wrapped the array in prose, extract the first JSON array.
    match = re.search(r"\[.*\]", content, re.DOTALL)
    if match:
        content = match.group(0)

    tickers = json.loads(content)
    if not isinstance(tickers, list) or not tickers:
        raise ValueError("LLM returned an invalid ticker list")

    return [str(t).strip().upper() for t in tickers if str(t).strip()]


def query_wig20_via_llm():
    """Ask the LLM for the current WIG20 constituents and their tickers."""
    if not LLM_API_KEY:
        raise RuntimeError("No LLM API key configured (set LLM_API_KEY).")

    prompt = (
        "List the current 20 companies that make up the WIG20 index (Warsaw "
        "Stock Exchange). Return ONLY a valid JSON array of their Yahoo "
        "Finance ticker symbols with the .WA suffix, for example "
        '["PKO.WA", "PKN.WA"]. Do not add any commentary.'
    )

    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        },
        timeout=30,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return _parse_tickers(content)


def refresh_wig20_tickers():
    """Re-query the LLM and update the on-disk cache (caller handles locking)."""
    tickers = query_wig20_via_llm()
    _save_cache({"tickers": tickers, "updated_at": time.time()})
    return tickers


def _get_fresh_cached():
    """Return cached tickers if still within the freshness window, else None."""
    cached = _load_cache()
    if not cached:
        return None
    tickers = cached.get("tickers")
    if not tickers:
        return None
    age = time.time() - float(cached.get("updated_at", 0) or 0)
    return tickers if age < MAX_CACHE_AGE_SECONDS else None


def get_wig20_tickers(force_refresh=False):
    """
    Return the current WIG20 ticker list (thread-safe).

    Uses the on-disk cache when fresh; otherwise re-queries the LLM. Falls back
    to the cached list, and finally the hardcoded list, if everything fails.
    """
    if not force_refresh:
        tickers = _get_fresh_cached()
        if tickers:
            return tickers

    with _refresh_lock:
        # Re-check the cache in case another thread refreshed while we waited.
        if not force_refresh:
            tickers = _get_fresh_cached()
            if tickers:
                return tickers

        try:
            return refresh_wig20_tickers()
        except Exception as e:
            print(f"[wig20] refresh failed ({e}); using fallback list")
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
    """
    Start a daemon thread that refreshes WIG20 constituents daily at midnight.

    Also performs an immediate best-effort refresh so the cache is warm on
    first launch without blocking any request.
    """
    def _run():
        # Initial warm-up refresh (best-effort, non-fatal).
        try:
            with _refresh_lock:
                refresh_wig20_tickers()
        except Exception as e:
            print(f"[wig20] initial refresh failed: {e}")

        while True:
            time.sleep(_seconds_until_next_midnight())
            try:
                with _refresh_lock:
                    refresh_wig20_tickers()
            except Exception as e:
                print(f"[wig20] scheduled refresh failed: {e}")

    thread = threading.Thread(target=_run, daemon=True, name="wig20-scheduler")
    thread.start()
    return thread
