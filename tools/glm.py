#!/usr/bin/env python3
"""Test a web-search-grounded prompt against Z.ai (GLM).

This file is named ``glm.py`` after the model family rather than ``zai.py``: a
script at ``tools/zai.py`` would shadow the installed ``zai`` SDK package in
``site-packages`` once ``tools/`` lands on ``sys.path`` (the default when running
``python tools/zai.py``), breaking ``from zai import ZaiClient``.

Z.ai has native web search. Two surfaces are available:

* **Web Search in Chat** -- pass a ``web_search`` tool to
  ``POST /paas/v4/chat/completions`` and the model answers with cited sources
  in a single call (search engine ``search_pro_jina``).
* **Web Search API** -- ``POST /paas/v4/web_search`` returns raw structured
  results (title/url/summary) without an LLM answer (search engine
  ``search-prime``).

Four approaches are demonstrated, crossing two dimensions -- implementation
(``requests`` vs the official ``zai-sdk``) and surface (Web Search in Chat vs
the standalone Web Search API):

1. ``requests-chat``   -- Web Search in Chat via raw HTTP.
2. ``requests-search`` -- standalone Web Search API via raw HTTP.
3. ``sdk-chat``        -- Web Search in Chat via the ``zai-sdk``.
4. ``sdk-search``      -- standalone Web Search API via the ``zai-sdk``.

Environment variables (see the project ``.env``):

    ZAI_API_KEY  Z.ai API key.
    ZAI_MODEL    Model name (default: ``glm-5.3``).

Usage::

    python tools/glm.py --approach requests-chat --prompt "Who won Euro 2024?"
    python tools/glm.py --approach sdk-search
"""

import argparse
import json
import os

import requests
from dotenv import load_dotenv

# Load .env into os.environ before reading keys, mirroring server/app.py.
load_dotenv()

ZAI_API_KEY = os.environ.get("ZAI_API_KEY", "")
ZAI_BASE_URL = "https://api.z.ai/api/paas/v4"
ZAI_CHAT_URL = f"{ZAI_BASE_URL}/chat/completions"
ZAI_WEB_SEARCH_URL = f"{ZAI_BASE_URL}/web_search"
ZAI_MODEL = os.environ.get("ZAI_MODEL", "glm-5.3-Flash")

# A question that benefits from live search grounding.
DEFAULT_PROMPT = (
    "What is the current Fed interest rate, and when was it last changed? "
    "Provide only the date of the last change and the rate value."
)


def _build_web_search_tool(query: str) -> dict:
    """Build the ``web_search`` tool entry for the chat-completions request."""
    return {
        "type": "web_search",
        "web_search": {
            # The chat tool only supports the "search_pro_jina" engine.
            "search_engine": "search_pro_jina",
            # A non-empty search_query forces the search to run for this query.
            "search_query": query,
            "enable": True,
            # Return the raw search results in the response (for citation info).
            "search_result": True,
        },
    }


def _extract_chat_content(data: dict) -> str:
    """Pull the assistant text out of an OpenAI-compatible chat response."""
    return data["choices"][0]["message"]["content"]


# --------------------------------------------------------------------------- #
# Shared SDK helper
# --------------------------------------------------------------------------- #
def _get_zai_client():
    """Build a ``ZaiClient``, with a helpful hint if the SDK isn't installed."""
    try:
        from zai import ZaiClient
    except ImportError as exc:
        raise SystemExit(
            "The 'zai-sdk' package is not installed. "
            "Install it with: pip install zai-sdk"
        ) from exc

    if not ZAI_API_KEY:
        raise RuntimeError("ZAI_API_KEY is not set. Add it to .env first.")
    return ZaiClient(api_key=ZAI_API_KEY)


# --------------------------------------------------------------------------- #
# Approach 1: requests + Web Search in Chat
# --------------------------------------------------------------------------- #
def zai_chat_with_web_search_requests(prompt: str) -> dict:
    """Call /chat/completions with the ``web_search`` tool via requests."""
    if not ZAI_API_KEY:
        raise RuntimeError("ZAI_API_KEY is not set. Add it to .env first.")

    response = requests.post(
        ZAI_CHAT_URL,
        headers={
            "Authorization": f"Bearer {ZAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": ZAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [_build_web_search_tool(prompt)],
            "stream": False,
        },
        timeout=240,
    )
    if not response.ok:
        raise RuntimeError(f"Z.ai returned {response.status_code}: {response.text}")
    return response.json()


def approach_requests_chat(prompt: str) -> None:
    """Web Search in Chat, via raw HTTP."""
    print("=" * 70)
    print("Approach: requests-chat (Z.ai chat + web_search tool)")
    print("=" * 70)

    print(f"\nAsking Z.ai ({ZAI_MODEL}) with web search for: {prompt!r}")
    data = zai_chat_with_web_search_requests(prompt)
    print("\n--- Z.ai answer ---")
    print(_extract_chat_content(data))

    print("\n--- Raw response (to inspect citations/search results) ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------- #
# Approach 2: requests + standalone Web Search API
# --------------------------------------------------------------------------- #
def zai_web_search_api_requests(prompt: str, count: int = 5) -> dict:
    """Call the standalone /web_search API (raw results, no LLM answer)."""
    if not ZAI_API_KEY:
        raise RuntimeError("ZAI_API_KEY is not set. Add it to .env first.")

    response = requests.post(
        ZAI_WEB_SEARCH_URL,
        headers={
            "Authorization": f"Bearer {ZAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            # The standalone API uses the "search-prime" engine.
            "search_engine": "search-prime",
            "search_query": prompt,
            "count": count,
        },
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"Z.ai returned {response.status_code}: {response.text}")
    return response.json()


def approach_requests_search(prompt: str) -> None:
    """Standalone Web Search API, via raw HTTP."""
    print("=" * 70)
    print("Approach: requests-search (standalone /web_search API)")
    print("=" * 70)

    print(f"\nSearching Z.ai Web Search API for: {prompt!r}")
    search = zai_web_search_api_requests(prompt)
    for i, item in enumerate(search.get("search_result", []), 1):
        print(f"[{i}] {item.get('title', '')}")
        print(f"    {item.get('link', '')}")
        print(f"    {item.get('content', '')[:200]}")


# --------------------------------------------------------------------------- #
# Approach 3: zai-sdk + Web Search in Chat
# --------------------------------------------------------------------------- #
def approach_sdk_chat(prompt: str) -> None:
    """Web Search in Chat, via the official Z.ai SDK."""
    print("=" * 70)
    print("Approach: sdk-chat (ZaiClient chat + web_search tool)")
    print("=" * 70)

    client = _get_zai_client()

    print(f"\nAsking Z.ai ({ZAI_MODEL}) with the web_search tool via SDK...")
    response = client.chat.completions.create(
        model=ZAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        tools=[_build_web_search_tool(prompt)],
        stream=False,
    )
    print("\n--- Z.ai answer ---")
    print(response.choices[0].message.content)


# --------------------------------------------------------------------------- #
# Approach 4: zai-sdk + standalone Web Search API
# --------------------------------------------------------------------------- #
def approach_sdk_search(prompt: str) -> None:
    """Standalone Web Search API, via the official Z.ai SDK."""
    print("=" * 70)
    print("Approach: sdk-search (client.web_search.web_search)")
    print("=" * 70)

    client = _get_zai_client()

    print(f"\nSearching Z.ai Web Search API (SDK) for: {prompt!r}")
    search = client.web_search.web_search(
        search_engine="search-prime",
        search_query=prompt,
        count=5,
    )
    if not search.search_result:
        print("No results found.")
        return
    for i, item in enumerate(search.search_result, 1):
        print(f"[{i}] {item.title}")
        print(f"    {item.link}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test a web-search-grounded prompt against Z.ai (GLM)."
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Question to answer (default: %(default)r)",
    )
    parser.add_argument(
        "--approach",
        choices=[
            "requests-chat",
            "requests-search",
            "sdk-chat",
            "sdk-search",
            "all",
        ],
        default="all",
        help="Which implementation to exercise (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    approaches = {
        "requests-chat": approach_requests_chat,
        "requests-search": approach_requests_search,
        "sdk-chat": approach_sdk_chat,
        "sdk-search": approach_sdk_search,
    }

    if args.approach == "all":
        for name, fn in approaches.items():
            print()
            fn(args.prompt)
    else:
        approaches[args.approach](args.prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
