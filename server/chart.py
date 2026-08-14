from flask import request, jsonify
from flask import Blueprint
from flask import render_template, session
from favs import get_favorites

from yfinance_imp import get_stock_ohlc_data, get_stock_ohlc_data_api


# refering to url from different module is url_for("news.news")
chart_bp = Blueprint("chart", __name__)

@chart_bp.context_processor
def inject_helpers():
    def is_favorite(symbol):
        favorites = get_favorites()
        return any(f.get("symbol") == symbol for f in favorites)
    
    return dict(is_favorite=is_favorite)

@chart_bp.route("/chartjs/<symbol>")
def chart(symbol):
    interval = "1d"  # default interval for initial load
    ohlc, name = get_stock_ohlc_data(symbol.upper(), interval)

    return render_template(
        "chartjs.html",
        chart_title=f"{symbol.upper()} Stocks",
        ohlc_data=ohlc,
        symbol=symbol.upper(),
        name=name,
    )


@chart_bp.route('/get_ohlc')
def get_data():
    interval = request.args.get('interval', '1d')
    symbol = request.args.get('symbol', 'AAPL')

    # print("interval " + interval);
    #period = '7d' if interval in ['1h', '4h'] else '1mo'
    ohlc = get_stock_ohlc_data_api(symbol, interval);

    # print([item["x"] for item in ohlc])
    # for row in data.itertuples();
     
    print(f'OHLC data count: {len(ohlc)}');
    return jsonify({'ohlc': ohlc})