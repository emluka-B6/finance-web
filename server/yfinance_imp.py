from datetime import datetime, timedelta, time
import yfinance as yf
from cache import load_cache, save_cache

MAX_BARS = 50

def fetch_with_backoff(symbol, interval, retries=5):
    for i in range(retries):
        try:
            return yf.download(symbol, interval=interval, period='5d')
        except yf.YFRateLimitError:
            wait = 2 ** i
            print(f"Rate limited, retrying in {wait} seconds...")
            time.sleep(wait)
    raise Exception("Exceeded maximum retries.")

def fetch_ohlc_data(symbol, interval, start_date, end_date):
    stock = yf.Ticker(symbol)

    shortname = stock.info.get("shortName", "<NoSymbolName>")
    hist = stock.history(start=start_date,
                         end=end_date, interval=interval)
    
    if hist.empty:
        print("[WARNING] No data returned for the specified date range!")

    return [
        {
            "x": d.strftime('%Y-%m-%dT%H:%M:%S'),
            "o": round(row['Open'], 2),
            "h": round(row['High'], 2),
            "l": round(row['Low'], 2),
            "c": round(row['Close'], 2),
        }
        for d, row in hist.iterrows()
    ], shortname

def merge_ohlc_data(existing_data, new_data, max_bars=MAX_BARS):
    merged = {point["x"]: point for point in existing_data}
    for point in new_data:
        merged[point["x"]] = point
    merged_sorted = sorted(merged.values(), key=lambda x: x["x"])
    return merged_sorted[-max_bars:]


HOURS_MAP = {
    "30m": 0.5,
    "1h": 1,
    "4h": 4,
    "1d": 24,
    "1wk": 7*24
}

def get_trading_days_date_range(interval: str):
    if interval not in HOURS_MAP:
        raise ValueError("Invalid interval")

    total_hours = HOURS_MAP[interval] * MAX_BARS
    end_date = datetime.now()

    # Adjust end date if it's weekend
    while end_date.weekday() >= 5:
        end_date -= timedelta(days=1)

    start_date = end_date
    remaining_hours = total_hours
    while remaining_hours > 0:
        start_date -= timedelta(hours=1)
        if start_date.weekday() < 5:
            remaining_hours -= 1

    return start_date, end_date

from zoneinfo import ZoneInfo  # built into Python 3.9+

MARKET_TZ = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

def is_trading_day(dt):
    """Return True if weekday (Mon–Fri)."""
    return dt.weekday() < 5

def is_trading_time(dt):
    """Return True if within 9:30–16:00 market hours."""
    return MARKET_OPEN <= dt.time() <= MARKET_CLOSE

def get_trading_hours_date_range(interval: str, end_date):
    if interval not in HOURS_MAP:
        raise ValueError("Invalid interval")

    step_hours = HOURS_MAP[interval]
    total_bars = MAX_BARS
    
    # Adjust end date to last trading time
    while not (is_trading_day(end_date) and is_trading_time(end_date)):
        end_date -= timedelta(minutes=30)  # move back in half-hour steps until valid

    bars = [end_date]

    # Walk backwards through time counting only trading intervals
    current = end_date
    while len(bars) < total_bars:
        current -= timedelta(hours=step_hours)

        # Only count if current time is within a trading session
        while not (is_trading_day(current) and is_trading_time(current)):
            current -= timedelta(minutes=30)
        bars.append(current)

    start_date = bars[-1]
    return start_date, end_date


def get_stock_ohlc_data(symbol, interval):
    start_date, end_date = get_trading_hours_date_range(interval, datetime.now(MARKET_TZ))
    # Extend end date for daily/weekly
    if interval in ["1d", "1wk"]:
        end_date = (end_date + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    cache = load_cache(symbol, interval)
    new_data, name = fetch_ohlc_data(symbol, interval, start_date, end_date)

    # print("new_data[-1].x " + str(new_data[-1]))
    combined = merge_ohlc_data(cache["data"], new_data)
    
    save_cache(symbol, name, interval, {
        "last_updated": end_date.isoformat(),
        "data": combined
    })
    return combined, name


def get_stock_ohlc_data_api(symbol, interval):
    start_dt, end_dt = get_trading_hours_date_range(interval, datetime.now(MARKET_TZ))
    
    # Extend end date for daily/weekly
    if interval in ["1d", "1wk"]:
        end_dt = (end_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # Use naive datetimes for yfinance
    start_str = start_dt.replace(tzinfo=None)
    end_str = end_dt.replace(tzinfo=None)

    print(f"start date {start_str}")
    print(f"end date {end_str}")
    new_data, name = fetch_ohlc_data(symbol, interval, start_str, end_str)

    print("new_data[-1].x " + str(new_data[-1]))
    return new_data

def update_ohlc_cache(symbol, interval, start_date, end_date):
    cache = load_cache(symbol, interval)
    cached = cache.get("data", [])

    if not cached:
        new_data, _ = fetch_ohlc_data(symbol, interval, start_date, end_date)
        return {"last_updated": end_date, "data": merge_ohlc_data([], new_data)}

    cached_x = sorted(p["x"] for p in cached)
    C_start, C_end = cached_x[0], cached_x[-1]
    R_start, R_end = start_date, end_date
    fetched = []

    # Case B — request fully covers cache, not use two fetches may be optimal
    if R_start < C_start and R_end >= C_end:
        fetched, _ = fetch_ohlc_data(symbol, interval, R_start, R_end)
    # Case C — missing left part
    elif R_start < C_start:
        fetched, _ = fetch_ohlc_data(symbol, interval, R_start, C_start)
    # Case D — missing right part
    elif R_end > C_end:
        fetched, _ = fetch_ohlc_data(symbol, interval, C_end, R_end)
    # Case E — fully cached
    else:
        fetched, _ = fetch_ohlc_data(symbol, interval, C_end, C_end)

    merged = merge_ohlc_data(cached, fetched)
    return {"last_updated": R_end, "data": merged}
