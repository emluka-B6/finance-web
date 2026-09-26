#!/usr/bin/env python3
"""Web search via Tavily (an external web-search provider).

Extracted from ``tools/deepseek.py`` so the Tavily plumbing can be reused -- and
exercised on its own -- without dragging in an LLM provider.

This file is deliberately **not** called ``tavily.py``: a script at
``tools/tavily.py`` would shadow the installed ``tavily`` SDK package in
``site-packages`` once ``tools/`` lands on ``sys.path`` (the default for
``python tools/tavily.py``), which is exactly the conflict ``tools/zai.py`` had
with the ``zai`` package before it was renamed to ``tools/glm.py``.

Two search implementations are provided, which ``tools/deepseek.py`` crosses
with a full grounded answer vs raw results:

1. ``requests`` -- raw ``POST https://api.tavily.com/search`` with a Bearer token.
2. ``sdk``      -- the ``tavily-python`` SDK (``TavilyClient.search``).

Environment variables (see the project ``.env``):

    TAVILY_API_KEY    Tavily search API key (required).

Usage::

    python tools/tavily_search.py --approach requests --prompt "Who won Euro 2024?"
    python tools/tavily_search.py --approach sdk
"""

import argparse
import os

import requests
from dotenv import load_dotenv

# Load .env into os.environ before reading keys, mirroring server/app.py.
load_dotenv()

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TAVILY_SEARCH_URL = "https://api.tavily.com/search"

# A question that only live web results can answer.
DEFAULT_PROMPT = (
    "What is the current Fed interest rate, and when was it last changed? "
    "Provide only the date of the last change and the rate value."
)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _get_tavily_client():
    """Build a ``TavilyClient``, with a helpful hint if the SDK isn't installed."""
    try:
        from tavily import TavilyClient
    except ImportError as exc:
        raise SystemExit(
            "The 'tavily-python' package is not installed. "
            "Install it with: pip install tavily-python"
        ) from exc

    if not TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is not set. Add it to .env first.")
    return TavilyClient(api_key=TAVILY_API_KEY)


def print_tavily_summary(search_payload: dict, max_chars: int = 600) -> None:
    """Print Tavily's own short LLM-generated answer for the query."""
    print(f"Tavily summary:\n {search_payload.get('answer', '')[:max_chars]}")


def print_results_detail(search_payload: dict) -> None:
    """Print a compact date/title/url/score line for every result found."""
    results = search_payload.get("results", [])
    print(f"Sources found:\n {len(results)}")
    for r in results:
        print(
            f'date: {r.get("published_date")}, title: {r.get("title")}, '
            f'\n                  url: {r.get("url")}, score: {r.get("score")}'
        )


def print_sources(search_payload: dict, max_content: int = 600) -> None:
    """Print Tavily results as numbered title/url/summary entries."""
    for i, result in enumerate(search_payload.get("results", []), 1):
        print(f"[{i}] {result.get('title', '')}")
        print(f"    {result.get('url', '')}")
        print(f"    {result.get('content', '')[:max_content]}")


# --------------------------------------------------------------------------- #
# Tavily search (requests + SDK)
# --------------------------------------------------------------------------- #
def tavily_search_requests(query: str, max_results: int = 5) -> dict:
    """Search the web with Tavily using a raw ``requests`` POST.

    Tavily's REST API is ``POST https://api.tavily.com/search`` with a Bearer
    token in the ``Authorization`` header and a JSON body. ``include_answer``
    asks Tavily to return a short LLM-generated answer alongside the raw
    results, which we pass through to the LLM for synthesis.
    """
    if not TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is not set. Add it to .env first.")

    response = requests.post(
        TAVILY_SEARCH_URL,
        headers={"Authorization": f"Bearer {TAVILY_API_KEY}"},
        json={
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "time_range": "week",
            "include_answer": True,
            "include_published_date": True,
            "topic": "news",  # or "general" (default) or "finance"
            # Use this only per concrete prompt. Maybe the best domain can be retrived from previous results ?
            # "include_domains": [
            #     "federalreserve.gov"
            # ],
            # "include_domains_mode": "prefer", # or restrict

            # "start_date": "2026-09-14",
            # "end_date": "2026-09-21",
            # Not all pages provides date, so this may filter relevant results
            # "filter_by_published_date": True,
        },
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(
            f"Tavily returned {response.status_code}: {response.text}"
        )
    return response.json()


def tavily_search_sdk(query: str, max_results: int = 5) -> dict:
    """Search the web with Tavily using the ``tavily-python`` SDK."""
    client = _get_tavily_client()
    # TavilyClient.search() returns a plain dict with "results"/"answer" keys.
    return client.search(
        query=query,
        search_depth="basic",  #or "advanced" +1 credit for search
        max_results=max_results,
        include_answer=True,
        time_range="week", #or "day"
        include_published_date=True,
    )


def search(query: str, approach: str = "requests", max_results: int = 5) -> dict:
    """Dispatch to the ``"requests"`` or ``"sdk"`` Tavily implementation."""
    if approach == "requests":
        return tavily_search_requests(query, max_results=max_results)
    if approach == "sdk":
        return tavily_search_sdk(query, max_results=max_results)
    raise ValueError(f"Unknown approach: {approach!r} (use 'requests' or 'sdk')")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def run_search(query: str, approach: str = "requests", max_results: int = 5) -> None:
    """Search Tavily and print the raw results (no LLM step)."""
    print("=" * 70)
    print(f"Approach: {approach}-search (Tavily {approach}, raw results)")
    print("=" * 70)

    print(f"\nSearching Tavily ({approach}) for:\n {query!r}")
    search_payload = search(query, approach=approach, max_results=max_results)
    print_tavily_summary(search_payload)
    print_results_detail(search_payload)
    print("\n--- Sources ---")
    print_sources(search_payload)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search the web with Tavily (requests or the tavily-python SDK)."
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Query to search for (default: %(default)r)",
    )
    parser.add_argument(
        "--approach",
        choices=["requests", "sdk", "all"],
        default="all",
        help="Tavily implementation to exercise (default: %(default)s)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximum number of results to request (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    approaches = (
        ["requests", "sdk"] if args.approach == "all" else [args.approach]
    )

    for approach in approaches:
        print()
        run_search(args.prompt, approach=approach, max_results=args.max_results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

