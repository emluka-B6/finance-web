import feedparser
import yfinance as yf
from flask import Blueprint, render_template
from datetime import datetime
from .favs import get_favorites_or_defaults
from .table import get_company_name

# refering to url from different module is url_for("news.news")
dashboard_bp = Blueprint("news", __name__)

def parse_feed(url, limit=5):
    """ Better, because format dates """
    
    feed = feedparser.parse(url)
    entries = feed.entries
    # Parse and sort by published date (descending)
    def parse_pubdate(entry):
        published = entry.get("published", "") or entry.get("updated", "")
        try:
            # Try multiple formats (RSS can vary)
            for fmt in ("%a, %d %b %Y %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    return datetime.strptime(published.replace(" +0000", ""), fmt)
                except ValueError:
                    continue
        except Exception:
            return datetime.min
        return datetime.min

    entries.sort(key=parse_pubdate, reverse=True)

    items = []
    for entry in entries[:limit]:
        published = entry.get("published", "")
        # Remove +0000 or similar timezone suffix
        published = published.replace(" +0000", "")
        items.append({
            "title": entry.get("title", "No title"),
            "link": entry.get("link", "#"),
            "published": published
        })
    return items


def parse_general_feed(limit=5):
    return parse_feed("https://finance.yahoo.com/news/rssindex", limit)

def parse_company_feed(ticker, limit=5):
    #depricated
    #"company": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL,MSFT,GOOGL&region=US&lang=en-US"
    return parse_feed(f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}", limit)


#Independent to Blueprint approach, when all filters are grouped in sub module 
# def register_filters(app):
    # app.jinja_env.filters["format_datetime"] = format_datetime

import pytz, time

@dashboard_bp.app_template_filter("format_datetime")
def format_datetime(value):
    if not value:
        return ""
    # Handle feedparser.struct_time or ISO string
    try:
        if isinstance(value, time.struct_time):
            dt = datetime(*value[:6])
        # Case 2: RFC-822 format (e.g. "Sun, 19 Oct 2025 14:37:19")
        elif isinstance(value, str) and "," in value:
            try:
                dt = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %z")
            except ValueError:
                # fallback if timezone missing
                dt = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S")
        # Case 3: ISO 8601 (e.g. "2025-10-19T14:17:17Z")
        elif isinstance(value, str) and "T" in value:
            try:
                dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        else:
            return str(value)
        
        dt = dt.astimezone(pytz.timezone("Europe/Warsaw"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception as e:
        print("Error formatting date:", e, "for value", value)
        return ""


@dashboard_bp.route("/news")
def news():
    tickers = ["AAPL", "MSFT", "GOOGL"]
    general_news = parse_general_feed(10)
    company_news = {
        ticker: parse_company_feed(ticker)
        for ticker in tickers
    }
    
    return render_template(
        "news.html",
        general_news=general_news,
        company_news=company_news
    )

@dashboard_bp.route("/news2")
def news2():
    favorites = get_favorites_or_defaults()
    tickers = [favorite["symbol"] for favorite in favorites]
    general_news = parse_general_feed(10)
    company_news = {
        ticker: parse_company_feed(ticker)
        for ticker in tickers
    }
    company_names = {
        ticker: get_company_name(ticker)
        for ticker in tickers
    }

    return render_template(
        "news2.html",
        general_news=general_news,
        company_news=company_news,
        company_names=company_names,
        favorites=favorites
    )