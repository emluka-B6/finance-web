"""
Generic LLM client (OpenAI-compatible API).

Central place for LLM provider/model configuration and request helpers so any
feature (not just the WIG20 constituents lookup) can talk to an LLM.

Configuration is driven by environment variables (used as defaults) and can be
overridden at runtime from the Settings page (in-memory, per-process):

    LLM_API_KEY   API key (required for LLM requests).
    LLM_PROVIDER  Provider key selecting the OpenAI-compatible base URL.
                  - openai:   https://api.openai.com/v1
                  - deepseek: https://api.deepseek.com/v1
                  - zai:      https://api.z.ai/api/paas/v4
    LLM_MODEL     Model name. Defaults to the first model of the provider.
    LLM_USE_WEB_SEARCH  "1"/"true" to ground requests in live web results via
                  the OpenAI Responses API web search tool. Defaults to enabled;
                  it only applies to the OpenAI endpoint and falls back to a
                  plain chat call otherwise.
"""
import os

import requests
from urllib.parse import urlparse

LLM_API_KEY_DICT = {
    "openai": os.environ.get("OPENAI_API_KEY"),
    "deepseek": os.environ.get("DEEPSEEK_API_KEY"),
    "zai": os.environ.get("ZAI_API_KEY")
}
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
        # deepseek-chat is the non-reasoning model (fast, cheap) and is the
        # right default for simple "return a JSON array" lookups. The others
        # are reasoning models that spend a long time in reasoning_content
        # before emitting the final answer, so they need a generous timeout.
        "models": ["deepseek-chat", "deepseek-flash", "deepseek-v4-pro"],
    },
    "zai": {
        "label": "Z.ai",
        "base_url": "https://api.z.ai/api/paas/v4",
        "models": ["glm-4.7-plus", "glm-5", "glm-5.1", "glm-5.2", "glm-5.3-flash", "glm-5.3"],
    },
}

# Environment defaults, used until the Settings page overrides them.
# _ENV_PROVIDER = os.environ.get("LLM_PROVIDER", "deepseek")
# _ENV_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
_ENV_PROVIDER = os.environ.get("LLM_PROVIDER", "zai")
_ENV_MODEL = os.environ.get("LLM_MODEL", "glm-5")
LLM_API_KEY = LLM_API_KEY_DICT.get(_ENV_PROVIDER) or os.environ.get("LLM_API_KEY")

# Runtime overrides set via the Settings page (in-memory "python variables").
# When None, the environment defaults above are used.
_selected_provider = None
_selected_model = None
_selected_api_key = None

LLM_USE_WEB_SEARCH = os.environ.get("LLM_USE_WEB_SEARCH", "1").lower() in ("1", "true", "yes")


def get_llm_provider():
    """Return the selected LLM provider key (runtime override or env default).

    Normalized to lowercase so a stray ``LLM_PROVIDER=DeepSeek`` (or a typo in
    the Settings page) cannot trigger a ``KeyError`` from the provider dicts,
    which are keyed by lowercase names.
    """
    provider = _selected_provider or _ENV_PROVIDER
    return (provider or "").strip().lower()


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

def get_configured_api_key(provider):
    """Return the API key for the specified provider."""
    return LLM_API_KEY_DICT.get(provider, None)

def set_llm_settings(provider, model):
    """Override the LLM provider/model selected in the Settings page.

    Raises ``ValueError`` for an unknown provider or a model not offered by it.
    """
    global _selected_provider, _selected_model, LLM_API_KEY
    if provider not in LLM_PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {provider!r}")
    if model not in LLM_PROVIDERS[provider]["models"]:
        raise ValueError(f"Unknown model {model!r} for provider {provider!r}")

    LLM_API_KEY = get_configured_api_key(provider)
    print(f"LLM_API_KEY set to: {LLM_API_KEY}")
    _selected_provider = provider
    _selected_model = model


def get_llm_api_key():
    """Return the API key (runtime override, or the environment default)."""
    print(f"Returning LLM_API_KEY: {LLM_API_KEY}")
    return _selected_api_key or LLM_API_KEY


def set_llm_api_key(api_key):
    """Override the LLM API key selected in the Settings page.

    An empty/blank value clears the override, falling back to ``LLM_API_KEY``.
    """
    global _selected_api_key
    _selected_api_key = (api_key or "").strip() or None


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
    print(f"Querying OpenAI-compatible chat API: {url}")
    
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
        # Reasoning models (e.g. deepseek-flash) can spend minutes in
        # reasoning_content before returning, so mirror the generous timeout
        # used by the web-search path rather than the previous 30s.
        timeout=240,
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
    provider = get_llm_provider()
    if provider != "zai":
        url = f"{get_llm_base_url().rstrip('/')}/chat/completions"
    else:
        url = f"{get_llm_base_url().rstrip('/')}/responses"

    print(f"Querying OpenAI Responses API with web search: {url}")
    
    if "openai.com" not in get_llm_base_url():
        raise RuntimeError("Web search is only supported with the OpenAI endpoint.")
    
    print(f"Model: {get_llm_model()}")

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
    print(f"OpenAI Responses API returned status {resp.status_code}")
    print(f"OpenAI Responses API response: {resp.json()}")

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
