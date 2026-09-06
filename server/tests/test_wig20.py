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

    def boom():
        raise RuntimeError("no key")

    monkeypatch.setattr(wig20, "query_wig20_via_llm", boom)
    assert wig20.get_wig20_tickers(force_refresh=True) == wig20.DEFAULT_WIG20_TICKERS
