import yfinance as yf
from functools import wraps, lru_cache
import time

def measure_time(label):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()

            result = func(*args, **kwargs)

            duration = time.perf_counter() - start
            print(f"{label}: {duration:.2f} seconds")
            return result
        return wrapper
    return decorator

# usage: @measure_time("Batch stock fetch")

# Function to fetch stock data for a list of tickers
def get_stocks_day_data(tickers):
    data = {}

    start = time.perf_counter()
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            # Extract relevant data
            data[ticker] = {
                'name': info.get('longName', 'N/A'),
                'current_price': info.get('regularMarketPrice', 0),
                'change': info.get('regularMarketChange', 0),
                'percent_change': info.get('regularMarketChangePercent', 0),
            }
        except Exception as e:
            data[ticker] = {
                'name': 'N/A',
                'current_price': 0,
                'change': 0,
                'percent_change': 0,
                'error': str(e)
            }

    end = time.perf_counter()
    print(f"New method: {end - start:.2f} seconds")

    data_date = 'N/A'
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="1d")
            if not hist.empty:
                data_date = hist.index[-1].strftime("%B %d, %Y")
                break  # Stop after first successful date fetch
        except Exception as e:
            continue        
    return data, data_date





def get_stock_day_data_yahoo(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Try to get real-time data
        current_price = info.get('regularMarketPrice', None)
        change = info.get('regularMarketChange', 0)
        percent_change = info.get('regularMarketChangePercent', 0)

        # If real-time data is unavailable, fall back to historical data
        if current_price is None:
            history = stock.history(period="1d")
            if not history.empty:
                last_date = history.index[-1].to_pydatetime().date()
                data_date = last_date.strftime("%B %d, %Y")
                current_price = history['Close'].iloc[-1]
                change = current_price - history['Close'].iloc[-2] if len(history) > 1 else 0
                percent_change = (change / history['Close'].iloc[-2]) * 100 if len(history) > 1 else 0

        return {
            'current_price': current_price if current_price is not None else 0,
            'change': change,
            'percent_change': percent_change,
            'data_date': data_date
        }
    except Exception as e:
        print("Error finance:" + str(e))
        return {
            'current_price': 0,
            'change': 0,
            'percent_change': 0,
            'data_date': 'N/A',
            'error': str(e)
        }

import requests

def get_stock_day_data_alpha_vantage(ticker, api_key = "AJJ8FS09XZGGJHWD"):
    # url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={api_key}"
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={api_key}'
    # Wyszukiwanie symboli: https://www.alphavantage.co/documentation/#symbolsearch
    #url = f'https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={text}&apikey={api_key}'

    response = requests.get(url)
    data = response.json()

    print("data \n:" + str(data))

    if "Global Quote" in data:
        quote = data["Global Quote"]
        return {
            'current_price': float(quote.get('05. price', 0)),
            'change': float(quote.get('09. change', 0)),
            'percent_change': float(quote.get('10. change percent', '0').strip('%'))
        }
    return {'current_price': 0, 'change': 0, 'percent_change': 0, 'error': 'Data not found'}

import requests

def get_stock_day_data_eod(ticker, api_key =  "67d605baaec202.06771411"):
    url = f"https://eodhistoricaldata.com/api/real-time/{ticker}?api_token={api_key}&fmt=json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        print(data)
        return {
            'current_price': float(data.get('close', 0)),
            'change': float(data.get('change', 0)),
            'percent_change': float(data.get('change_pct', 0)),
            'error': ""
        }
    return {'current_price': 0, 'change': 0, 'percent_change': 0, 'error': str(response.status_code)}


import nasdaqdatalink as ndl
# import pandas as pd

def get_stock_day_data_nasdaq(api_key =  "aSmXpZ4dMpiqzQdQzSb9"):
    # Set your API key (replace 'your_api_key' with your actual key)
    ndl.ApiConfig.api_key = api_key

    # Fetch historical WIG20 data from Warsaw Stock Exchange
    data = ndl.get("WARSAWSE/WIG20")

    # Display the first few rows
    print(data.head())

    # Optional: Save data to CSV
    # data.to_csv("wig20_data.csv")

    return {'current_price': 0, 'change': 0, 'percent_change': 0, 'error': 'API error'}

import pandas_datareader.data as web
from datetime import datetime, timedelta

def get_stock_day_data_stooq(ticker):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=5)
    
    start_date = datetime(2025, 3, 11)  # Tuesday
    end_date = datetime(2025, 3, 14)    # Friday (last trading day before March 16)
    try:
        wig20_data = web.DataReader(ticker, 'stooq', start_date, end_date)
        wig20_data = wig20_data.sort_index()
        
        print("DataFrame info:")
        print(wig20_data.info())  # Shows structure even if empty
        print("DataFrame content:")
        print(wig20_data)

        latest_close = wig20_data['Close'].iloc[-1]
        previous_close = wig20_data['Close'].iloc[-2]
        change = latest_close - previous_close
        percent_change = (change / previous_close) * 100
        
        result = {
            "current_price": round(latest_close, 2),
            "change": round(change, 2),
            "percent_change": round(percent_change, 2),
            "error": ""
        }
        return result
    except Exception as e:
        return {'current_price': 0, 'change': 0, 'percent_change': 0, 'error': str(e)}