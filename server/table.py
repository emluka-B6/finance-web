
# Routes for stock indexes
from functools import lru_cache

import json
import os
import time
from flask import Blueprint, render_template
import yfinance as yf
import pandas as pd

from .wig20 import get_wig20_tickers

table_bp = Blueprint("table", __name__)

COMPANY_NAMES_CACHE_FILE = os.environ.get(
    "COMPANY_NAMES_CACHE_FILE", "cache/company_names.json"
)
# Company names change very rarely; refresh at most once a week.
COMPANY_NAMES_TTL = 7 * 24 * 60 * 60


def _load_company_names():
    try:
        with open(COMPANY_NAMES_CACHE_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_company_names(cache):
    try:
        os.makedirs(os.path.dirname(COMPANY_NAMES_CACHE_FILE) or ".", exist_ok=True)
        with open(COMPANY_NAMES_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except OSError as e:
        print(f"[company_names] could not write cache: {e}")


@lru_cache(maxsize=256)
def get_company_info(ticker):
    """Return (short_name, long_name) for a ticker, falling back to the ticker.

    Names are fetched once from Yahoo Finance and then persisted on disk (with
    a TTL) plus cached in memory per process, so the menu/table don't trigger a
    network round-trip on every request.
    """
    cache = _load_company_names()
    entry = cache.get(ticker)
    if entry and (time.time() - float(entry.get("updated_at", 0) or 0)) < COMPANY_NAMES_TTL:
        return entry.get("short", ticker), entry.get("long", ticker)

    try:
        info = yf.Ticker(ticker).info
        short = info.get("shortName") or ticker
        long = info.get("longName") or short
    except Exception:
        # Don't cache failures so a transient error can be retried later.
        return ticker, ticker

    cache[ticker] = {"short": short, "long": long, "updated_at": time.time()}
    _save_company_names(cache)
    return short, long


def get_company_short_name(ticker):
    """Human-friendly short name (e.g. "Orlen") used in the navigation menu."""
    return get_company_info(ticker)[0]


def get_company_name(ticker):
    """Full company name (e.g. "Orlen S.A.") used in tables."""
    return get_company_info(ticker)[1]
    

def get_stocks_day_data_opt(tickers):
    """
    Fetch latest daily data for multiple tickers efficiently.
    Returns a dictionary of {ticker: {price, change, percent_change, name}}.
    """

    start = time.perf_counter()
  
    # Batch download (1 call for all tickers)
    hist = yf.download(tickers=tickers, period="2d", interval="1d", 
                       group_by='ticker', progress=False, threads=True)
    
    end = time.perf_counter()
    print(f"New method: {end - start:.2f} seconds")
    
    results = {}
    data_date = None

    for ticker in tickers:
        try:
            if isinstance(hist.columns, pd.MultiIndex):
                df = hist[ticker]
            else:
                df = hist

            if len(df) < 2:
                raise ValueError("Not enough data")

            prev_close = df['Close'].iloc[-2]
            last_close = df['Close'].iloc[-1]

            change = last_close - prev_close
            percent_change = (change / prev_close) * 100 if prev_close else 0

            results[ticker] = {
                'name': get_company_name(ticker),
                'current_price': round(last_close, 2),
                'change': round(change, 2),
                'percent_change': round(percent_change, 2),
            }

            if data_date is None:
                data_date = df.index[-1].strftime("%B %d, %Y")

        except Exception as e:
            results[ticker] = {
                'name': get_company_name(ticker),
                'current_price': 0,
                'change': 0,
                'percent_change': 0,
                'error': str(e)
            }

    return results, data_date

@table_bp.route('/wig20')
def wig20():
    # Current constituents are queried (and cached) instead of hardcoded.
    wig20_tickers = get_wig20_tickers()
    
    # data = get_stock_data('^WIG20')  # Ticker for WIG20
    # data = get_stock_data_alpha_vantage('WIG20')  # Ticker for WIG20
    # data = get_stock_data_stooq('^WIG20') # Ticker for WIG20
    # data = get_stock_data_nasdaq()        # Ticker for WIG20
    # data = get_stock_data_eod('^WIG20')   # Ticker for WIG20

    # Fetch data for each stock
    stock_data, data_date = get_stocks_day_data_opt(wig20_tickers)

    return render_template('table.html', table_title="WIG 20", data_date=data_date, 
                           stock_data=stock_data)

@table_bp.route('/mag7')
def mag7():
    mag7_tickers = ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'NVDA', 'TSLA', 'META']

    stock_data, data_date = get_stocks_day_data_opt(mag7_tickers)    
    return render_template('table.html', table_title="NASDAQ 7", data_date=data_date, 
                           stock_data=stock_data)