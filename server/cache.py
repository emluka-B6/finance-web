import os
import json

CACHE_DIR = "cache"

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def get_cache_path(symbol, interval):
    safe_symbol = symbol.replace("/", "_")  # For symbols like "BTC/USD"
    return os.path.join(CACHE_DIR, f"{safe_symbol}_{interval}.json")

def load_cache(symbol, interval):
    path = get_cache_path(symbol, interval)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {"last_updated": None, "data": []}

def save_cache(symbol, name, interval, cache_data):
    path = get_cache_path(symbol, interval)
    with open(path, "w") as f:
        json.dump(cache_data, f)
