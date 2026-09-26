#!/usr/bin/env python3
"""Web search via Parallel (Parallel Web Systems' Search API).

Mirrors ``tools/tavily_search.py`` for a second provider, so both can be queried
and compared with the same shapes. Parallel is objective-first: you send an
``objective`` (the question) plus short keyword ``search_queries`` and it returns
relevance-ranked excerpts already compressed for an LLM. There is no Tavily-style
"answer" field -- the excerpts are what you feed to a model.

This file is deliberately **not** called ``parallel.py``: the official SDK ships
as the ``parallel`` module (``pip install parallel-web``), so ``tools/parallel.py``
would shadow it once ``tools/`` lands on ``sys.path`` -- the same conflict that
``tools/tavily_search.py`` and ``tools/glm.py`` avoid.

Latest news: the Search API limits results by publication date through
``advanced_settings.source_policy.after_date`` (``--news`` / ``--after-date``
below) and can skip cached index content for fresher pages through
``advanced_settings.fetch_policy`` (``--live``).

Two search implementations are provided:

1. ``requests`` -- raw ``POST https://api.parallel.ai/v1/search`` (``x-api-key``).
2. ``sdk``      -- the ``parallel-web`` SDK (``from parallel import Parallel``).

Environment variables (see the project ``.env``):

    PARALLEL_API_KEY    Parallel API key (required).

Usage::

    python tools/parallel_search.py --approach requests
    python tools/parallel_search.py --approach sdk --mode advanced
    python tools/parallel_search.py --approach requests --news 3 --live
"""

import argparse
import datetime
import os

import requests
from dotenv import load_dotenv

# Load .env into os.environ before reading keys, mirroring server/app.py.
load_dotenv()

PARALLEL_API_KEY = os.environ.get("PARALLEL_API_KEY", "")
PARALLEL_SEARCH_URL = "https://api.parallel.ai/v1/search"

# Search modes, ordered by latency and cost. "fast" (~700ms) is Parallel's
# recommendation for most agents; the API defaults to "advanced" when omitted.
PARALLEL_MODES = ("turbo", "fast", "basic", "advanced")
DEFAULT_MODE = "fast"

# Public Search modes cap results at 20 (the API default is 10).
DEFAULT_MAX_RESULTS = 10
MAX_RESULTS_CAP = 20

# Freshness knobs: ``after_date`` filters by publication date; fetch_policy's
# minimum ``max_age_seconds`` is 600 (10 minutes), so anything fresher means a
# live fetch instead of cached index content.
DEFAULT_NEWS_DAYS = 7
LIVE_MAX_AGE_SECONDS = 600

# The same question the other tools ask, so providers can be compared directly.
DEFAULT_OBJECTIVE = (
    "What is the current Fed interest rate, and when was it last changed? "
    "Provide only the date of the last change and the rate value."
)
DEFAULT_SEARCH_QUERIES = [
    "Fed interest rate",
    "federal funds rate change",
    "latest FOMC decision",
]


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _get_parallel_client():
    """Build a ``Parallel`` client, with a hint if the SDK isn't installed."""
    try:
        from parallel import Parallel
    except ImportError as exc:
        raise SystemExit(
            "The 'parallel-web' package is not installed. "
            "Install it with: pip install parallel-web"
        ) from exc

    if not PARALLEL_API_KEY:
        raise RuntimeError("PARALLEL_API_KEY is not set. Add it to .env first.")
    return Parallel(api_key=PARALLEL_API_KEY)


def news_after_date(days: int = DEFAULT_NEWS_DAYS) -> str:
    """RFC 3339 ``YYYY-MM-DD`` date ``days`` back, for latest-news filtering."""
    return (datetime.date.today() - datetime.timedelta(days=days)).isoformat()


def _normalise_queries(search_queries) -> list:
    """Accept a list or a comma-separated string of keyword queries."""
    if not search_queries:
        return []
    if isinstance(search_queries, str):
        search_queries = search_queries.split(",")
    return [str(query).strip() for query in search_queries if str(query).strip()]


def build_advanced_settings(
    max_results: int = DEFAULT_MAX_RESULTS,
    after_date: str | None = None,
    location: str | None = None,
    live: bool = False,
) -> dict:
    """Assemble the ``advanced_settings`` object from the individual knobs."""
    settings: dict = {}
    if max_results:
        settings["max_results"] = max_results
    if after_date:
        # Search-API-only freshness filter (earliest publication date).
        settings["source_policy"] = {"after_date": after_date}
        # before_date — only sources published before a given date.
        # allowed_domains — restrict results to specified domains.
        # blocked_domains — exclude specified domains.
    if live:
        # Anything younger than the minimum age forces a live page fetch, otherwise cached page
        settings["fetch_policy"] = {"max_age_seconds": LIVE_MAX_AGE_SECONDS}
        # max_chars_total  → how much fetched content to process
    if location:
        settings["location"] = location
    return settings


def build_payload(
    objective: str | None = None,
    search_queries = None,
    mode: str = DEFAULT_MODE,
    max_results: int = DEFAULT_MAX_RESULTS,
    after_date: str | None = None,
    location: str | None = None,
    live: bool = False,
) -> dict:
    """Build the JSON body for ``POST /v1/search`` (also the SDK kwargs)."""
    payload: dict = {
        "search_queries": _normalise_queries(search_queries)
        or DEFAULT_SEARCH_QUERIES,
    }
    if objective:
        payload["objective"] = objective
    if mode:
        payload["mode"] = mode
    advanced_settings = build_advanced_settings(
        max_results=max_results,
        after_date=after_date,
        location=location,
        live=live,
    )
    # payload["session_id"] #for reuse if multiple similar calles
    # payload["client_model"] #to optimize output for llm
    if advanced_settings:
        payload["advanced_settings"] = advanced_settings
    return payload


def print_results_detail(search_payload: dict) -> None:
    """Print a compact date/title/url line for every result found."""
    results = search_payload.get("results", [])
    print(f"Results found:\n {len(results)}")
    for r in results:
        print(
            f'date: {r.get("publish_date")}, title: {r.get("title")}, '
            f'\n                  url: {r.get("url")}'
        )


def _excerpt_text(result: dict) -> str:
    """Join a result's ``excerpts`` list into a single line."""
    excerpts = result.get("excerpts") or []
    return " ... ".join(str(excerpt).replace("\n", " ") for excerpt in excerpts)


def print_sources(search_payload: dict, max_chars: int = 600) -> None:
    """Print Parallel results as numbered title/url/excerpt entries."""
    for i, result in enumerate(search_payload.get("results", []), 1):
        print(f"[{i}] {result.get('title', '')}")
        print(f"    {result.get('url', '')}")
        print(f"    {_excerpt_text(result)[:max_chars]}")


def print_usage(search_payload: dict) -> None:
    """Print input-validation warnings and the billed usage entries, if any."""
    warnings = search_payload.get("warnings")
    if warnings:
        print(f"\n--- Warnings ---\n {warnings}")
    usage = search_payload.get("usage")
    if usage:
        print(f"\n--- Usage ---\n {usage}")


# --------------------------------------------------------------------------- #
# Parallel search (requests + SDK)
# --------------------------------------------------------------------------- #
def parallel_search_requests(
    objective: str | None = None,
    search_queries=None,
    mode: str = DEFAULT_MODE,
    max_results: int = DEFAULT_MAX_RESULTS,
    after_date: str | None = None,
    location: str | None = None,
    live: bool = False,
) -> dict:
    """Search the web with Parallel using a raw ``requests`` POST.

    Parallel's REST API is ``POST https://api.parallel.ai/v1/search`` with the
    key in the ``x-api-key`` header and the objective/queries in the JSON body.
    The timeout is generous because ``advanced`` mode plus a live fetch can take
    close to a minute.
    """
    if not PARALLEL_API_KEY:
        raise RuntimeError("PARALLEL_API_KEY is not set. Add it to .env first.")

    response = requests.post(
        PARALLEL_SEARCH_URL,
        headers={
            "x-api-key": PARALLEL_API_KEY,
            "Content-Type": "application/json",
        },
        json=build_payload(
            objective=objective,
            search_queries=search_queries,
            mode=mode,
            max_results=max_results,
            after_date=after_date,
            location=location,
            live=live,
        ),
        timeout=120,
    )
    if not response.ok:
        raise RuntimeError(
            f"Parallel returned {response.status_code}: {response.text}"
        )
    return response.json()


def parallel_search_sdk(
    objective: str | None = None,
    search_queries=None,
    mode: str = DEFAULT_MODE,
    max_results: int = DEFAULT_MAX_RESULTS,
    after_date: str | None = None,
    location: str | None = None,
    live: bool = False,
) -> dict:
    """Search the web with Parallel using the ``parallel-web`` SDK."""
    client = _get_parallel_client()
    # The SDK mirrors the REST body one-for-one, so the payload doubles as kwargs.
    result = client.search(
        **build_payload(
            objective=objective,
            search_queries=search_queries,
            mode=mode,
            max_results=max_results,
            after_date=after_date,
            location=location,
            live=live,
        )
    )
    # SDK responses are Pydantic models; the requests path returns plain dicts.
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result


def search(
    objective: str | None = None,
    search_queries=None,
    approach: str = "requests",
    mode: str = DEFAULT_MODE,
    max_results: int = DEFAULT_MAX_RESULTS,
    after_date: str | None = None,
    location: str | None = None,
    live: bool = False,
) -> dict:
    """Dispatch to the ``"requests"`` or ``"sdk"`` Parallel implementation."""
    options = dict(
        mode=mode,
        max_results=max_results,
        after_date=after_date,
        location=location,
        live=live,
    )
    if approach == "requests":
        return parallel_search_requests(objective, search_queries, **options)
    if approach == "sdk":
        return parallel_search_sdk(objective, search_queries, **options)
    raise ValueError(f"Unknown approach: {approach!r} (use 'requests' or 'sdk')")

# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def run_search(
    objective: str | None = None,
    search_queries=None,
    approach: str = "requests",
    mode: str = DEFAULT_MODE,
    max_results: int = DEFAULT_MAX_RESULTS,
    after_date: str | None = None,
    location: str | None = None,
    live: bool = False,
) -> None:
    """Search Parallel and print the raw results (no LLM step)."""
    print("=" * 70)
    print(f"Approach: {approach}-search (Parallel {approach}, raw results)")
    print("=" * 70)

    print(f"\nSearching Parallel ({approach}, mode={mode}) for:\n {objective!r}")
    queries = _normalise_queries(search_queries) or DEFAULT_SEARCH_QUERIES
    print(f"Queries: {', '.join(queries)}")
    if after_date:
        print(f"Published after: {after_date}")
    if live:
        print(f"Live fetch: enabled (max_age_seconds={LIVE_MAX_AGE_SECONDS})")
    if location:
        print(f"Location: {location}")

    search_payload = search(
        objective,
        search_queries=search_queries,
        approach=approach,
        mode=mode,
        max_results=max_results,
        after_date=after_date,
        location=location,
        live=live,
    )
    print_results_detail(search_payload)
    print("\n--- Sources ---")
    print_sources(search_payload)
    print_usage(search_payload)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search the web with Parallel (requests or the parallel-web SDK)."
    )
    parser.add_argument(
        "--objective",
        "--prompt",
        dest="objective",
        default=DEFAULT_OBJECTIVE,
        help="Natural-language goal driving the search (default: %(default)r)",
    )
    parser.add_argument(
        "--queries",
        default=", ".join(DEFAULT_SEARCH_QUERIES),
        help="Comma-separated keyword queries, 3-6 words each (default: %(default)r)",
    )
    parser.add_argument(
        "--approach",
        choices=["requests", "sdk", "all"],
        default="all",
        help="Parallel implementation to exercise (default: %(default)s)",
    )
    parser.add_argument(
        "--mode",
        choices=list(PARALLEL_MODES),
        default=DEFAULT_MODE,
        help="Search mode preset, lowest latency first (default: %(default)s)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=DEFAULT_MAX_RESULTS,
        help=f"Upper bound on results, API cap {MAX_RESULTS_CAP} "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--news",
        type=int,
        nargs="?",
        const=DEFAULT_NEWS_DAYS,
        default=None,
        metavar="DAYS",
        help="Only latest news: keep results published in the last DAYS days "
        f"(default: {DEFAULT_NEWS_DAYS})",
    )
    parser.add_argument(
        "--after-date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Earliest publication date; overrides --news",
    )
    parser.add_argument(
        "--location",
        default=None,
        metavar="CC",
        help="ISO 3166-1 alpha-2 country code for geo-targeted results, "
        'e.g. "us", "pl", "gb"',
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Skip cached index content via "
        f"fetch_policy.max_age_seconds={LIVE_MAX_AGE_SECONDS}; fresher but slower",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    after_date = args.after_date
    if after_date is None and args.news is not None:
        after_date = news_after_date(args.news)
    approaches = ["requests", "sdk"] if args.approach == "all" else [args.approach]

    for approach in approaches:
        print()
        run_search(
            args.objective,
            args.queries,
            approach=approach,
            mode=args.mode,
            max_results=args.max_results,
            after_date=after_date,
            location=args.location,
            live=args.live,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
