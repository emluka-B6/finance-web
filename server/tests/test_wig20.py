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


def test_get_wig20_tickers_falls_back_to_default_when_no_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(wig20, "WIG20_CACHE_FILE", str(tmp_path / "cache.json"))
    assert wig20.get_wig20_tickers() == wig20.DEFAULT_WIG20_TICKERS


def test_cache_is_stale_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(wig20, "WIG20_CACHE_FILE", str(tmp_path / "cache.json"))
    assert wig20._cache_is_stale() is True


def test_cache_is_stale_when_updated_on_an_earlier_day(tmp_path, monkeypatch):
    monkeypatch.setattr(wig20, "WIG20_CACHE_FILE", str(tmp_path / "cache.json"))
    with open(tmp_path / "cache.json", "w") as f:
        json.dump({"tickers": ["AAA.WA"], "updated_at": time.time() - 2 * 24 * 3600}, f)
    assert wig20._cache_is_stale() is True


def test_cache_is_not_stale_when_updated_today(tmp_path, monkeypatch):
    monkeypatch.setattr(wig20, "WIG20_CACHE_FILE", str(tmp_path / "cache.json"))
    with open(tmp_path / "cache.json", "w") as f:
        json.dump({"tickers": ["AAA.WA"], "updated_at": time.time()}, f)
    assert wig20._cache_is_stale() is False


def test_normalize_tickers_fixes_orlen_alias():
    assert wig20._normalize_tickers(["ORLEN.WA", "PKO.WA"]) == ["PKN.WA", "PKO.WA"]


def test_normalize_tickers_adds_suffix_and_dedupes():
    assert wig20._normalize_tickers(["PKN", "PKN.WA", "  pko  "]) == ["PKN.WA", "PKO.WA"]


def test_normalize_tickers_drops_invalid():
    assert wig20._normalize_tickers(["ABCDEF", "ab"]) == []


def _responses_payload():
    """Minimal OpenAI Responses API payload exercising both URL sources."""
    return {
        "output_text": '["PKO.WA"]',
        "output": [
            {
                "type": "web_search_call",
                "action": {
                    "sources": [
                        {"url": "https://www.gpw.pl/a", "title": "GPW A",
                         "hostname": "www.gpw.pl"},
                        {"url": "https://www.gpw.pl/b", "title": "GPW B",
                         "hostname": "www.gpw.pl"},
                        {"url": "https://www.reddit.com/r/x", "title": "Reddit",
                         "hostname": "www.reddit.com"},
                        {"url": "https://stooq.pl", "title": "Stooq", "hostname": "stooq.pl"},
                    ]
                },
            },
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "The answer",
                        "annotations": [
                            {"type": "url_citation", "url": "https://www.gpw.pl/a",
                             "title": "GPW A", "hostname": "www.gpw.pl"},
                        ],
                    }
                ],
            },
        ],
    }


def test_extract_urls_splits_cited_and_searched():
    cited, searched = wig20._extract_urls(_responses_payload())
    assert [e["url"] for e in cited] == ["https://www.gpw.pl/a"]
    assert [e["url"] for e in searched] == [
        "https://www.gpw.pl/a",
        "https://www.gpw.pl/b",
        "https://www.reddit.com/r/x",
        "https://stooq.pl",
    ]


def test_source_entry_extracts_hostname_from_url_when_missing():
    entry = wig20._source_entry({"url": "https://www.Gpw.pl/path", "title": "t"})
    assert entry["hostname"] == "gpw.pl"
    assert entry["url"] == "https://www.Gpw.pl/path"


def test_dedupe_by_hostname_keeps_first_per_hostname():
    entries = [
        {"url": "https://a.com/1", "hostname": "a.com"},
        {"url": "https://a.com/2", "hostname": "a.com"},
        {"url": "https://b.com/1", "hostname": "b.com"},
    ]
    result = wig20._dedupe_by_hostname(entries)
    assert [e["url"] for e in result] == ["https://a.com/1", "https://b.com/1"]


def test_filter_noise_drops_denylisted_hostnames():
    entries = [
        {"url": "https://gpw.pl", "hostname": "gpw.pl"},
        {"url": "https://reddit.com/r/x", "hostname": "reddit.com"},
    ]
    result = wig20._filter_noise(entries, {"reddit.com"})
    assert [e["url"] for e in result] == ["https://gpw.pl"]
