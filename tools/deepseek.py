#!/usr/bin/env python3
"""Test a web-search-grounded prompt against DeepSeek using Tavily.

DeepSeek's API has no built-in web-search tool, so live results are pulled from
Tavily (an external web-search provider) and passed to DeepSeek as context. The
Tavily plumbing itself lives in ``tools/tavily_search.py``; this script adds the
DeepSeek step and the four comparison approaches on top of it.

Four approaches are demonstrated, crossing two dimensions -- the Tavily search
implementation (``requests`` vs the ``tavily-python`` SDK, both imported from
``tools/tavily_search.py``) and the surface (full grounded answer vs raw search
results):

1. ``requests-chat``   -- Tavily via ``requests``, then a grounded DeepSeek answer.
2. ``requests-search`` -- Tavily via ``requests``, raw results only (no LLM).
3. ``sdk-chat``        -- Tavily via ``tavily-python``, then a grounded DeepSeek answer.
4. ``sdk-search``      -- Tavily via ``tavily-python``, raw results only (no LLM).

DeepSeek chat stays on ``requests`` in every approach because DeepSeek ships no
official Python SDK (its API is OpenAI-compatible).

Environment variables (see the project ``.env``):

    TAVILY_API_KEY    Tavily search API key (required for the search step).
    DEEPSEEK_API_KEY  DeepSeek API key.
    DEEPSEEK_MODEL    Model name (default: ``deepseek-flash``).

Usage::

    python tools/deepseek.py --approach requests-chat --prompt "Who won Euro 2024?"
    python tools/deepseek.py --approach sdk-search

    # Raw Tavily results only, without DeepSeek:
    python tools/tavily_search.py --approach sdk
"""

import argparse
import os

import requests
from dotenv import load_dotenv

# Tavily search lives in ``tools/tavily_search.py`` so it can be reused, and run
# on its own, without this DeepSeek wrapper. Running ``python tools/deepseek.py``
# puts ``tools/`` on ``sys.path``, so the bare import resolves; importing this
# module as ``tools.deepseek`` from the project root needs the fallback below.
try:  # ``python tools/deepseek.py``
    import tavily_search
except ImportError:  # ``import tools.deepseek``
    from tools import tavily_search

# Load .env into os.environ before reading keys, mirroring server/app.py.
load_dotenv()

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_CHAT_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")

# A question DeepSeek cannot answer from its training data alone, forcing it to
# rely on the live Tavily results we provide.
DEFAULT_PROMPT = (
    "What is the current Fed interest rate, and when was it last changed? "
    "Provide only the date of the last change and the rate value."
)


# --------------------------------------------------------------------------- #
# DeepSeek chat (requests)
# --------------------------------------------------------------------------- #
def deepseek_answer_requests(prompt: str, search_payload: dict) -> str:
    """Ask DeepSeek to answer ``prompt`` grounded in ``search_payload``."""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not set. Add it to .env first.")

    # Build a compact context block from Tavily's structured results.
    results = search_payload.get("results", [])
    context = "\n\n".join(
        f"[{i + 1}] {r.get('title', '')}\n{r.get('url', '')}\n{r.get('content', '')}"
        for i, r in enumerate(results)
    )
    tavily_answer = search_payload.get("answer", "")

    system = (
        "You are a helpful assistant. Answer the user's question using ONLY the "
        "web search results provided below. Cite sources by their [number] when "
        "you use them. If the results do not contain the answer, say so."
    )
    user = (
        f"Question: {prompt}\n\n"
        f"Tavily's own summary: {tavily_answer}\n\n"
        f"Web search results:\n{context}"
    )

    response = requests.post(
        DEEPSEEK_CHAT_URL,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        },
        timeout=240,
    )
    if not response.ok:
        raise RuntimeError(
            f"DeepSeek returned {response.status_code}: {response.text}"
        )
    return response.json()["choices"][0]["message"]["content"]


def approach_requests_chat(prompt: str) -> None:
    """Tavily via requests, then a grounded DeepSeek answer via requests."""
    print("=" * 70)
    print("Approach: requests-chat (Tavily requests -> DeepSeek requests)")
    print("=" * 70)

    print(f"\nSearching Tavily (requests) for:\n {prompt!r}")
    search_payload = tavily_search.tavily_search_requests(prompt)
    tavily_search.print_tavily_summary(search_payload)
    tavily_search.print_results_detail(search_payload)

    print(f"\nAsking DeepSeek ({DEEPSEEK_MODEL})...")
    answer = deepseek_answer_requests(prompt, search_payload)
    print("\n--- DeepSeek answer ---")
    print(answer)


# --------------------------------------------------------------------------- #
# Approach 2: requests + raw search results only
# --------------------------------------------------------------------------- #
def approach_requests_search(prompt: str) -> None:
    """Tavily via requests, printing raw results (no LLM answer)."""
    print("=" * 70)
    print("Approach: requests-search (Tavily requests, raw results)")
    print("=" * 70)

    print(f"\nSearching Tavily (requests) for:\n {prompt!r}")
    search_payload = tavily_search.tavily_search_requests(prompt)
    tavily_search.print_tavily_summary(search_payload)
    print("\n--- Sources ---")
    tavily_search.print_sources(search_payload)


# --------------------------------------------------------------------------- #
# Approach 3: SDK + full grounded answer (chat)
# --------------------------------------------------------------------------- #
def approach_sdk_chat(prompt: str) -> None:
    """Tavily via SDK, then a grounded DeepSeek answer via requests."""
    print("=" * 70)
    print("Approach: sdk-chat (Tavily SDK -> DeepSeek requests)")
    print("=" * 70)

    print(f"\nSearching Tavily (SDK) for:\n {prompt!r}")
    search_payload = tavily_search.tavily_search_sdk(prompt)
    tavily_search.print_tavily_summary(search_payload)
    tavily_search.print_results_detail(search_payload)

    print(f"\nAsking DeepSeek ({DEEPSEEK_MODEL})...")
    answer = deepseek_answer_requests(prompt, search_payload)
    print("\n--- DeepSeek answer ---")
    print(answer)


# --------------------------------------------------------------------------- #
# Approach 4: SDK + raw search results only
# --------------------------------------------------------------------------- #
def approach_sdk_search(prompt: str) -> None:
    """Tavily via SDK, printing raw results (no LLM answer)."""
    print("=" * 70)
    print("Approach: sdk-search (Tavily SDK, raw results)")
    print("=" * 70)

    print(f"\nSearching Tavily (SDK) for:\n {prompt!r}")
    search_payload = tavily_search.tavily_search_sdk(prompt)
    tavily_search.print_tavily_summary(search_payload)
    print("\n--- Sources ---")
    tavily_search.print_sources(search_payload)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test a web-search-grounded prompt against DeepSeek via Tavily."
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
