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
