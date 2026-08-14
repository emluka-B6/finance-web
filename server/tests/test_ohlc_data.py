from yfinance_imp import merge_ohlc_data
from datetime import datetime

def test_merge_basic():
    existing = [
        {"x": 1, "o": 10},
        {"x": 3, "o": 30},
    ]
    new = [
        {"x": 2, "o": 20},
        {"x": 4, "o": 40},
    ]

    result = merge_ohlc_data(existing, new, max_bars=10)

    assert [p["x"] for p in result] == [1, 2, 3, 4]

def test_merge_overwrites_existing():
    existing = [
        {"x": 1, "o": 10},
        {"x": 2, "o": 20},
    ]
    new = [
        {"x": 2, "o": 999},
    ]

    result = merge_ohlc_data(existing, new, max_bars=10)

    assert len(result) == 2
    assert next(p for p in result if p["x"] == 2)["o"] == 999

def test_merge_respects_max_bars():
    existing = [{"x": i, "o": i} for i in range(10)]
    new = []

    result = merge_ohlc_data(existing, new, max_bars=5)

    assert [p["x"] for p in result] == [5, 6, 7, 8, 9]

def test_merge_new_data_pushes_out_old():
    existing = [{"x": i, "o": i} for i in range(5)]
    new = [{"x": 5, "o": 5}, {"x": 6, "o": 6}]

    result = merge_ohlc_data(existing, new, max_bars=5)

    assert [p["x"] for p in result] == [2, 3, 4, 5, 6]

def test_merge_only_new_data():
    new = [{"x": 1, "o": 10}, {"x": 2, "o": 20}]
    result = merge_ohlc_data([], new, max_bars=10)
    assert result == new

from unittest.mock import patch
from yfinance_imp import update_ohlc_cache

@patch("yfinance_imp.fetch_ohlc_data")
@patch("yfinance_imp.load_cache")
def test_update_empty_cache(mock_cache, mock_fetch):
    mock_cache.return_value = {"last_updated": None, "data": []}
    mock_fetch.return_value = (
        [{"x": "2025-10-18T11:00"}, {"x": "2025-10-18T12:00"}],
        "Apple"
    )
    result = update_ohlc_cache("AAPL", "1h", "2025-10-18T11:00", "2025-10-18T12:00")

    mock_fetch.assert_called_once_with(
        "AAPL", "1h", "2025-10-18T11:00", "2025-10-18T12:00"
    )
    assert [p["x"] for p in result["data"]] == [
        "2025-10-18T11:00",
        "2025-10-18T12:00",
    ]

@patch("yfinance_imp.fetch_ohlc_data")
@patch("yfinance_imp.load_cache")
def test_update_partial_cache(mock_cache, mock_fetch):
    mock_cache.return_value = {
        "last_updated": None,
        "data": [{"x": "2025-10-18T10:00"}, {"x": "2025-10-18T11:00", "o": 1}]
    }
    mock_fetch.return_value = (
        [{"x": "2025-10-18T11:00", "o": 2}, {"x": "2025-10-18T12:00"}, {"x": "2025-10-18T13:00"}],
        "Apple"
    )

    result = update_ohlc_cache("AAPL", "1d", "2025-10-18T10:00", "2025-10-18T13:00")
    mock_fetch.assert_called_once_with("AAPL", "1d", "2025-10-18T11:00", "2025-10-18T13:00")
    assert len(result["data"]) == 4
    assert result["data"][1]["o"] == 2 # fetched value overwrite cached


@patch("yfinance_imp.fetch_ohlc_data")
@patch("yfinance_imp.load_cache")
def test_update_only_middle_in_cache(mock_cache, mock_fetch):
    mock_cache.return_value = {
        "last_updated": None,
        "data": [{"x": "2025-10-18T11:00", "o": 1}, {"x": "2025-10-18T12:00", "o": 1}]
    }
    mock_fetch.return_value = (
        [{"x": "2025-10-18T10:00"}, {"x": "2025-10-18T11:00", "o": 2},
         {"x": "2025-10-18T12:00", "o": 2}, {"x": "2025-10-18T13:00"}],
        "Apple"
    )

    result = update_ohlc_cache("AAPL", "1d", "2025-10-18T10:00", "2025-10-18T13:00")
    # Fetch overlaps last cached item, because in the past it was current value and value should be 
    # updated to be ensured
    mock_fetch.assert_called_once_with("AAPL", "1d", "2025-10-18T10:00", "2025-10-18T13:00")
    assert len(result["data"]) == 4
    assert result["data"][1]["o"] == 2 # fetched value overwrite cached
    assert result["data"][2]["o"] == 2 # fetched value overwrite cached

@patch("yfinance_imp.fetch_ohlc_data")
@patch("yfinance_imp.load_cache")
def test_update_fully_cached_range(mock_cache, mock_fetch):
    mock_cache.return_value = {
        "last_updated": None,
        "data": [{"x": "2025-10-18T10:00"}, {"x": "2025-10-18T11:00", "o": 1}]
    }
    mock_fetch.return_value = (
        [{"x": "2025-10-18T10:00"},{"x": "2025-10-18T11:00", "o": 2}],
        "Apple"
    )

    result = update_ohlc_cache("AAPL", "1d", "2025-10-18T10:00", "2025-10-18T11:00")
    mock_fetch.assert_called_once_with("AAPL", "1d", "2025-10-18T11:00", "2025-10-18T11:00")
    assert len(result["data"]) == 2
    assert result["data"][1]["o"] == 2 # fetched value overwrite cached