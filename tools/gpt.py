#!/usr/bin/env python3
"""Test a web-search-grounded prompt against OpenAI (GPT).

This file is named ``gpt.py`` after the model family rather than ``openai.py``:
a script at ``tools/openai.py`` would shadow the installed ``openai`` SDK
package in ``site-packages`` once ``tools/`` lands on ``sys.path`` (the default
when running ``python tools/gpt.py``), breaking ``from openai import OpenAI`` --
the same conflict ``tools/glm.py``, ``tools/tavily_search.py`` and
``tools/parallel_search.py`` avoid.

OpenAI has native **web search** as a built-in tool. Unlike Z.ai, there is no
standalone search endpoint that returns raw results: the only surface is the
``web_search`` tool attached to a model call, so the meaningful axis here is
*with* vs *without* web search, crossed with the implementation (``requests``
vs the official ``openai`` SDK):

1. ``requests-web``   -- Responses API + ``web_search`` tool via raw HTTP.
2. ``requests-plain`` -- plain Chat Completions (no tools) via raw HTTP.
3. ``sdk-web``        -- Responses API + ``web_search`` via the ``openai`` SDK.
4. ``sdk-plain``      -- plain Chat Completions via the ``openai`` SDK.

Web search in Chat -- ``POST /v1/responses`` with::

    "tools": [{"type": "web_search"}]

The current tool name is ``web_search``; the older ``web_search_preview`` is
still accepted for legacy integrations but ignores the newer controls
(``filters``, ``search_context_size``). ``tool_choice`` defaults to ``auto``
and lets the model decide whether to search, so this script pins it to the
search tool to guarantee grounding. ``include`` asks the response to carry
every source the tool retrieved (``web_search_call.action.sources``), while the
URLs actually cited in the answer come back as ``url_citation`` annotations --
the same two lists ``server/llm.py`` extracts.

Chat Completions can also search, but only through dedicated search models
(e.g. ``gpt-5-search-api``, ``gpt-4o-search-preview``) rather than the plain
``tools`` array; the Responses API is the recommended path and is what this
script uses.

Environment variables (see the project ``.env``):

    OPENAI_API_KEY  OpenAI API key.
    OPENAI_MODEL    Model name (default: ``gpt-4o``).

Usage::

    python tools/gpt.py --approach requests-web --prompt "Who won Euro 2024?"
    python tools/gpt.py --approach sdk-plain
"""

import argparse
import json
import os
from typing import Any, cast
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

# Load .env into os.environ before reading keys, mirroring server/app.py.
load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_RESPONSES_URL = f"{OPENAI_BASE_URL}/responses"
OPENAI_CHAT_URL = f"{OPENAI_BASE_URL}/chat/completions"
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")

# Web-search calls can spend minutes on reasoning models before returning, so
# mirror the generous timeout used by server/llm.py for both paths.
REQUEST_TIMEOUT = 240

# A question that benefits from live search grounding.
DEFAULT_PROMPT = (
    "What is the current Fed interest rate, and when was it last changed? "
    "Provide only the date of the last change and the rate value."
)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _build_web_search_tool() -> dict[str, str]:
    """Build the ``web_search`` tool entry for a Responses API request."""
    return {"type": "web_search"}


def _extract_chat_content(data: dict) -> str:
    """Pull the assistant text out of an OpenAI-compatible chat response."""
    return data["choices"][0]["message"]["content"]


def _extract_response_text(data: dict) -> str:
    """Extract the assistant's text from an OpenAI Responses API payload."""
    if data.get("output_text"):
        return data["output_text"]

    parts = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for block in item.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") in ("output_text", "text"):
                parts.append(block.get("text", ""))
    return "".join(parts)


def _source_entry(src: dict) -> dict:
    """Normalize a web-search source/annotation dict into a URL entry."""
    url = src.get("url") or ""
    hostname = (src.get("hostname") or "").lower().lstrip("www.")
    if not hostname:
        hostname = urlparse(url).netloc.lower().lstrip("www.")
    return {"url": url, "title": src.get("title") or "", "hostname": hostname}


def _extract_sources(data: dict) -> tuple:
    """Collect URLs from an OpenAI Responses API payload.

    Returns a tuple ``(cited, searched)`` of URL entry dicts::

        {"url": str, "title": str, "hostname": str}

    ``cited`` are the URLs referenced in the assistant's final answer
    (``url_citation`` annotations); ``searched`` are every source the web-search
    tool retrieved (``web_search_call.action.sources``).
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


def _print_sources(data: dict) -> None:
    """Print the cited URLs and the raw sources the search tool retrieved."""
    cited, searched = _extract_sources(data)

    print("\n--- Cited URLs (url_citation annotations) ---")
    if not cited:
        print("(none -- the model answered without citing a source)")
    for i, entry in enumerate(cited, 1):
        print(f"[{i}] {entry['title']}")
        print(f"    {entry['url']}")

    print("\n--- Searched sources (web_search_call.action.sources) ---")
    if not searched:
        print("(none -- the response contains no web_search_call item)")
    for i, entry in enumerate(searched, 1):
        print(f"[{i}] {entry['title']}")
        print(f"    {entry['url']}")


# --------------------------------------------------------------------------- #
# requests implementation
# --------------------------------------------------------------------------- #
def openai_response_with_web_search_requests(prompt: str) -> dict:
    """Call the Responses API with the ``web_search`` tool via requests."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env first.")

    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "input": prompt,
            "tools": [_build_web_search_tool()],
            # Force a search instead of leaving it to the model's judgement.
            "tool_choice": {"type": "web_search"},
            # Return every source read by the tool, for citation diagnostics.
            "include": ["web_search_call.action.sources"],
        },
        timeout=REQUEST_TIMEOUT,
    )
    if not response.ok:
        raise RuntimeError(f"OpenAI returned {response.status_code}: {response.text}")
    return response.json()


def openai_chat_plain_requests(prompt: str) -> str:
    """Call plain Chat Completions (no tools) via requests."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env first.")

    response = requests.post(
        OPENAI_CHAT_URL,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=REQUEST_TIMEOUT,
    )
    if not response.ok:
        raise RuntimeError(f"OpenAI returned {response.status_code}: {response.text}")
    return _extract_chat_content(response.json())


# --------------------------------------------------------------------------- #
# openai-sdk implementation
# --------------------------------------------------------------------------- #
def _get_openai_client():
    """Build an ``OpenAI`` client, with a hint if the SDK isn't installed."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit(
            "The 'openai' package is not installed. "
            "Install it with: pip install openai"
        ) from exc

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env first.")
    return OpenAI(api_key=OPENAI_API_KEY)


def openai_response_with_web_search_sdk(prompt: str) -> dict:
    """Call the Responses API with the ``web_search`` tool via the SDK."""
    client = _get_openai_client()

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
        tools=[cast(Any, _build_web_search_tool())],
        tool_choice=cast(Any, {"type": "web_search"}),
        include=["web_search_call.action.sources"],
    )
    # Normalize the typed SDK objects back to a plain dict so the same
    # extraction/printing helpers work for both implementations. ``output_text``
    # is a computed convenience property, so it is not part of the dump.
    return response.model_dump()


def openai_chat_plain_sdk(prompt: str) -> str | None:
    """Call plain Chat Completions (no tools) via the SDK."""
    client = _get_openai_client()

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    if response is None or not response.choices:
        print("OpenAI SDK returned no choices in the response.")
        return None
    return response.choices[0].message.content


# --------------------------------------------------------------------------- #
# Approach 1: requests + web search
# --------------------------------------------------------------------------- #
def approach_requests_web(prompt: str) -> None:
    """Responses API + web_search tool, via raw HTTP."""
    print("=" * 70)
    print("Approach: requests-web (Responses API + web_search tool)")
    print("=" * 70)

    print(f"\nAsking OpenAI ({OPENAI_MODEL}) with web search for: {prompt!r}")
    data = openai_response_with_web_search_requests(prompt)
    print("\n--- OpenAI answer ---")
    print(_extract_response_text(data))
    _print_sources(data)

    print("\n--- Raw response (to inspect citations/search results) ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------- #
# Approach 2: requests + no web search
# --------------------------------------------------------------------------- #
def approach_requests_plain(prompt: str) -> None:
    """Plain Chat Completions (no tools), via raw HTTP."""
    print("=" * 70)
    print("Approach: requests-plain (Chat Completions, no web search)")
    print("=" * 70)

    print(f"\nAsking OpenAI ({OPENAI_MODEL}) without web search for: {prompt!r}")
    print("\n--- OpenAI answer ---")
    print(openai_chat_plain_requests(prompt))


# --------------------------------------------------------------------------- #
# Approach 3: openai SDK + web search
# --------------------------------------------------------------------------- #
def approach_sdk_web(prompt: str) -> None:
    """Responses API + web_search tool, via the official OpenAI SDK."""
    print("=" * 70)
    print("Approach: sdk-web (OpenAI SDK responses.create + web_search)")
    print("=" * 70)

    print(f"\nAsking OpenAI ({OPENAI_MODEL}) with web search via SDK...")
    data = openai_response_with_web_search_sdk(prompt)
    print("\n--- OpenAI answer ---")
    print(_extract_response_text(data))
    _print_sources(data)


# --------------------------------------------------------------------------- #
# Approach 4: openai SDK + no web search
# --------------------------------------------------------------------------- #
def approach_sdk_plain(prompt: str) -> None:
    """Plain Chat Completions (no tools), via the official OpenAI SDK."""
    print("=" * 70)
    print("Approach: sdk-plain (OpenAI SDK chat.completions, no web search)")
    print("=" * 70)

    print(f"\nAsking OpenAI ({OPENAI_MODEL}) without web search via SDK...")
    print("\n--- OpenAI answer ---")
    response = openai_chat_plain_sdk(prompt)
    if response:
        print(response is not None and response or "")

# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test a web-search-grounded prompt against OpenAI (GPT), "
        "with and without the native web_search tool."
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Question to answer (default: %(default)r)",
    )
    parser.add_argument(
        "--approach",
        choices=[
            "requests-web",
            "requests-plain",
            "sdk-web",
            "sdk-plain",
            "all",
        ],
        default="all",
        help="Which implementation to exercise (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    approaches = {
        "requests-web": approach_requests_web,
        "requests-plain": approach_requests_plain,
        "sdk-web": approach_sdk_web,
        "sdk-plain": approach_sdk_plain,
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
