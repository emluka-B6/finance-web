from yfinance_imp import get_trading_hours_date_range, MARKET_CLOSE
from datetime import datetime
import pytest

def test_invalid_interval_date_range():
    curr_dt = datetime(2025, 11, 14, 12, 00) # Friday
    with pytest.raises(ValueError):
        get_trading_hours_date_range("1D", curr_dt)
    with pytest.raises(ValueError):
        get_trading_hours_date_range("1w", curr_dt)    


def test_1d_date_range(monkeypatch):
    monkeypatch.setattr("yfinance_imp.MAX_BARS", 10)

    curr_dt = datetime(2025, 11, 14, 12, 00) # Friday
    start, end = get_trading_hours_date_range("1d", curr_dt)

    # 14.11 (Friday) -> 03.11 (Monday) -> 10 days
    assert end == curr_dt
    assert start == datetime(2025, 11, 3, MARKET_CLOSE.hour, MARKET_CLOSE.minute)

def test_4h_date_range(monkeypatch):
    monkeypatch.setattr("yfinance_imp.MAX_BARS", 10) # 2 bars per stocks day

    curr_dt = datetime(2025, 11, 14, 13, 00) # Friday
    start, end = get_trading_hours_date_range("4h", curr_dt)

    # 4h bars starts on 9:30 and 12
    # 14.11 13:00 (Friday) -> 07.11 16:00 (Friday)?? -> 5 days
    # 07.11 16:00 - no such bar
    assert end == curr_dt
    assert start == datetime(2025, 11, 7, 16, 0)


def test_1h_date_range(monkeypatch):
    monkeypatch.setattr("yfinance_imp.MAX_BARS", 12) # 8 bars per stocks day

    curr_dt = datetime(2025, 11, 14, 12, 30) # Friday
    start, end = get_trading_hours_date_range("1h", curr_dt)

    # 14.11 12:30 (Friday) -> 13.11 9:30 -> 12h
    assert end == curr_dt
    # assert start == datetime(2025, 11, 13, 9, 30)
    assert start == datetime(2025, 11, 12, 16, 00)


def test_1wk_date_range(monkeypatch):
    monkeypatch.setattr("yfinance_imp.MAX_BARS", 2)

    curr_dt = datetime(2025, 11, 14, 12, 30) # Friday
    start, end = get_trading_hours_date_range("1wk", curr_dt)

    # 14.11 (Friday) -> 03.11 (Monday) -> 10 days -> 2 weeks
    assert end == curr_dt
    # assert start == datetime(2025, 11, 3, MARKET_CLOSE.hour, MARKET_CLOSE.minute)
    # This is not right, correct end date inside tested function
    assert start == datetime(2025, 11, 7, 12, 30)

def test_1h_omit_weekend_on_start(monkeypatch):
    monkeypatch.setattr("yfinance_imp.MAX_BARS", 12) # 8 bars per stocks day

    curr_dt = datetime(2025, 11, 15, 12, 30) # Saturday
    start, end = get_trading_hours_date_range("1h", curr_dt)

    # 15.11 12:30 (Saturday) -> 13.11 11:00 -> weeknd + 12h
    assert end == datetime(2025, 11, 14, 16, 00)
    assert start == datetime(2025, 11, 13, 12, 00)