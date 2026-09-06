import json
import time

import pytest

import server.wig20 as wig20


def test_parse_tickers_plain():
    assert wig20._parse_tickers('["PKO.WA", "PKN.WA"]') == ["PKO.WA", "PKN.WA"]


def test_parse_tickers_strips_code_fence():
    content = '```json\n["PKO.WA", "PKN.WA"]\n```'
    assert wig20._parse_tickers(content) == ["PKO.WA", "PKN.WA"]


def test_parse_tickers_extracts_array_from_prose():
    content = 'Here is the list: ["PKO.WA", "PKN.WA"] hope it helps.'
    assert wig20._parse_tickers(content) == ["PKO.WA", "PKN.WA"]


def test_parse_tickers_invalid_raises():
    with pytest.raises(ValueError):
        wig20._parse_tickers("no array here")


def test_get_wig20_tickers_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(wig20, "WIG20_CACHE_FILE", str(tmp_path / "cache.json"))
    tickers = ["AAA.WA", "BBB.WA"]
    with open(tmp_path / "cache.json", "w") as f:
        json.dump({"tickers": tickers, "updated_at": time.time()}, f)
    assert wig20.get_wig20_tickers() == tickers


def test_get_wig20_tickers_falls_back_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(wig20, "WIG20_CACHE_FILE", str(tmp_path / "cache.json"))
    monkeypatch.setattr(wig20, "DIAGNOSTICS_LOG_FILE", str(tmp_path / "diag.jsonl"))

    def boom(diag):
        raise RuntimeError("no key")

    monkeypatch.setattr(wig20, "query_wig20_via_llm", boom)
    assert wig20.get_wig20_tickers(force_refresh=True) == wig20.DEFAULT_WIG20_TICKERS


def test_normalize_tickers_fixes_orlen_alias():
    assert wig20._normalize_tickers(["ORLEN.WA", "PKO.WA"]) == ["PKN.WA", "PKO.WA"]


def test_normalize_tickers_adds_suffix_and_dedupes():
    assert wig20._normalize_tickers(["PKN", "PKN.WA", "  pko  "]) == ["PKN.WA", "PKO.WA"]


def test_normalize_tickers_drops_invalid():
    assert wig20._normalize_tickers(["ABCDEF", "ab"]) == []


def test_normalize_one():
    assert wig20._normalize_one("ORLEN.WA") == "PKN.WA"
    assert wig20._normalize_one("pko") == "PKO.WA"
    assert wig20._normalize_one("ABCDEF") is None


def test_is_clean_ticker():
    assert wig20._is_clean_ticker("PKO.WA") is True
    assert wig20._is_clean_ticker("PKO") is True
    assert wig20._is_clean_ticker("ORLEN.WA") is False
    assert wig20._is_clean_ticker("PKO Bank Polski") is False


def test_extract_urls_from_web_search_output():
    data = {
        "output": [
            {
                "type": "web_search_call",
                "action": {
                    "sources": [
                        {"url": "https://example.com/a", "title": "A"},
                        {"url": "https://example.com/b", "title": "B"},
                        {"url": "https://example.com/a", "title": "A dup"},
                    ]
                },
            },
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "...",
                        "annotations": [
                            {"type": "url_citation", "url": "https://example.com/c"}
                        ],
                    }
                ],
            },
        ]
    }
    assert wig20._extract_urls(data) == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]


def test_diagnostics_to_dict():
    d = wig20.Wig20Diagnostics(model="gpt-4o-mini")
    d.source = "web_search"
    d.visited_urls = ["https://x"]
    d.json_ok = True
    d.ticker_count = 20
    out = d.to_dict()
    assert out["model"] == "gpt-4o-mini"
    assert out["count_mismatch"] is False
    assert out["visited_urls"] == ["https://x"]
