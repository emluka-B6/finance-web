import requests, hashlib
from flask import request, jsonify, Blueprint, session
from flask_login import current_user
from misc.alchemy_db import Favorite
from misc.extensions import db

# refering to url from different module is url_for("news.news")
fav_bp = Blueprint("favs", __name__)

HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://finance.yahoo.com/",
        "Origin": "https://finance.yahoo.com",
        "Accept-Language": "en-US,en;q=0.9",
    }

def request_yahoo_ticker(query):    
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        if (not response.ok):
            return [], "No data"

        data = response.json()
        results = [
            {
                "symbol": item["symbol"],
                "name": item.get("shortname", item.get("longname", item["symbol"])),
                "exchange": item.get("exchange", "")
            }
            for item in data.get("quotes", [])
        ]
        return results, ""
    except Exception as e:
        print(str(e))
        return [], str(e)

@fav_bp.route("/search_ticker")
def search_ticker():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    
    resultArray, state = request_yahoo_ticker(query)
    if (state == ""):
        return jsonify(resultArray)
    else:
        return jsonify({"error": state}), 500
    
import json, os, time

CACHE_DIR = "cache/ticker_search"
CACHE_FILE = "ticker_cache.json"
CACHE_TTL = 3600 * 12  # 12 hours

os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_path(query):
    key = hashlib.md5(query.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{key}.json")

def load_cache(query):
    cache_path = get_cache_path(query)
    # --- load from cache if valid ---
    if os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < CACHE_TTL:
        with open(cache_path, "r") as f:
            return json.load(f)
    return []

def save_cache(query, data):
    cache_path = get_cache_path(query)
    with open(cache_path, "w") as f:
        json.dump(data, f)




import yfinance as yf
from datetime import datetime, timezone
DEFAULT_FAVORITES = [
    {"symbol": "AAPL", "name": "Apple"},
    {"symbol": "MSFT", "name": "Microsoft"},
    {"symbol": "GOOGL", "name": "Alphabet"},
]



def get_ticker_fast_snapshot(name, ticker):
    fast = ticker.fast_info
    price = fast.get("last_price", 0) or 0

    if price != 0:
        change = fast.get("regular_market_change_percent", 0) or 0
        last_ts = fast.get("last_market_time", None)
        return name, price, change, last_ts

    return name, price, 0, 0

def get_ticker_slow_snapshot(name, ticker):
    try:
        info = ticker.info
        price = info.get("regularMarketPrice", 0)
        if price != 0:
            shortname = info.get("shortName", name),
            change = info.get("regularMarketChangePercent", 0)
            last_ts = info.get("regularMarketTime", None)
            # print(f'slow info price {price} for symbol {shortname}')
            return shortname, price, change, last_ts
    except Exception:
        pass

    return name, 0, 0, 0

def get_ticker_history_snapshot(name, ticker):
    try:
        hist = ticker.history(period="2d", interval="1d")
        if len(hist) >= 2:
            price = hist["Close"].iloc[-1]
            print(f'history price {price} for symbol {name}')
            prev = hist["Close"].iloc[-2]
            change = (price - prev) / prev * 100 if prev != 0 else 0
            last_ts = hist.index[-1].to_pydatetime().replace(tzinfo=timezone.utc)
            return name, price, change, last_ts
    except Exception:
        pass

    return name, 0, 0, 0

def format_time_str(last_ts):
    if last_ts: 
        try:
            if isinstance(last_ts, (int, float)):  # timestamp from info
                dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
            else:
                dt = last_ts
            time_str = dt.astimezone().strftime("%H:%M")
        except Exception:
            #todo current zone
            time_str = datetime.now().strftime("%H:%M")
    else:
        time_str = datetime.now().strftime("%H:%M")
    return time_str
    
def get_snapshot(favorites):
    """Fetch current stock data (name, price, change, time)."""
    
    stocks = yf.Tickers(" ".join(item["symbol"] for item in favorites))
    data = []
    for symbol, ticker in stocks.tickers.items():
        name, price, change, last_ts = get_ticker_fast_snapshot(symbol, ticker)
        if price == 0:
            name, price, change, last_ts = get_ticker_slow_snapshot(symbol, ticker)
        if price == 0:
            name, price, change, last_ts = get_ticker_history_snapshot(symbol, ticker)
    
        time_str = format_time_str(last_ts)
        
        data.append({
            "symbol": symbol,
            "name": name,
            "price": round(price, 2),
            "change": round(change, 2),
            "time": time_str,
        })
    return data

@fav_bp.route("/get_favorites")
def get_favorites():
    if current_user.is_authenticated:
        return [
            {"symbol": favorite.symbol, "name": favorite.name}
            for favorite in Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.id)
        ]

    return session.get("guest_favorites", [])


def get_favorites_or_defaults():
    """Return saved favourites, or the default symbols for a new session."""
    favorites = get_favorites()
    return favorites or DEFAULT_FAVORITES

@fav_bp.route("/favorites_data")
def favorites_data():
    favorites = get_favorites_or_defaults()
    result = get_snapshot(favorites)
    return jsonify(result)

@fav_bp.route("/search_ttl_cache_ticker")
def search_ttl_cache_ticker():
    query = request.args.get("q", "").strip().lower()
    cache = load_cache(query)
    if (len(cache)):
        print(f'Use cache for {query} result len is {len(cache)}')
        return jsonify(cache)
    
    results, state = request_yahoo_ticker(query)
    if (state == ""):
        save_cache(query, results)
        return jsonify(results)
    else:
        return jsonify({"error": state}), 500

@fav_bp.route("/toggle_favorite/<symbol>", methods=["POST"])
def toggle_favorite(symbol):
    name = request.args.get("name", symbol)
    if current_user.is_authenticated:
        existing = Favorite.query.filter_by(user_id=current_user.id, symbol=symbol).first()
        if existing:
            db.session.delete(existing)
            status = "removed"
        else:
            db.session.add(Favorite(user_id=current_user.id, symbol=symbol, name=name)) # type: ignore
            status = "added"
        db.session.commit()
    else:
        favorites = get_favorites()
        existing = next((f for f in favorites if f["symbol"] == symbol), None)
        if existing:
            favorites = [f for f in favorites if f["symbol"] != symbol]
            status = "removed"
        else:
            favorites.append({"symbol": symbol, "name": name})
            status = "added"

        session["guest_favorites"] = favorites
        session.modified = True

    return jsonify({"status": status})