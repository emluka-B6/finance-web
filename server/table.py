
# Routes for stock indexes
from functools import lru_cache

import time
from flask import Blueprint, render_template
import yfinance as yf
import pandas as pd

from .wig20 import get_wig20_tickers

table_bp = Blueprint("table", __name__)

@lru_cache(maxsize=128)
def get_company_name(ticker):
    try:
        return yf.Ticker(ticker).info.get('longName', ticker)
    except Exception:
        return ticker
    

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
                'name': ticker,
                'current_price': round(last_close, 2),
                'change': round(change, 2),
                'percent_change': round(percent_change, 2),
            }

            if data_date is None:
                data_date = df.index[-1].strftime("%B %d, %Y")

        except Exception as e:
            results[ticker] = {
                'name': ticker,
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