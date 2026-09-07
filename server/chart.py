from flask import request, jsonify, redirect, url_for
from flask import Blueprint
from flask import render_template
from flask_login import current_user
from .favs import get_favorites

from .yfinance_imp import get_stock_ohlc_data, get_stock_ohlc_data_api, fetch_ohlc_data
from .table import get_company_name


# refering to url from different module is url_for("news.news")
chart_bp = Blueprint("chart", __name__)

CHART_PROVIDERS = {
    "chartjs": "chart",
    "lightweight": "lightweight_chart",
}
DEFAULT_CHART_PROVIDER = "chartjs"

@chart_bp.app_context_processor
def inject_helpers():
    def is_favorite(symbol):
        favorites = get_favorites()
        return any(f.get("symbol") == symbol for f in favorites)
    
    return dict(is_favorite=is_favorite)


@chart_bp.route("/chart/<symbol>")
def selected_chart(symbol):
    """Open a chart with the provider selected for this browser session."""
    provider = (
        current_user.chart_provider
        if current_user.is_authenticated
        else DEFAULT_CHART_PROVIDER
    )
    endpoint = CHART_PROVIDERS.get(provider, CHART_PROVIDERS[DEFAULT_CHART_PROVIDER])
    return redirect(url_for(f"chart.{endpoint}", symbol=symbol))

@chart_bp.route("/chartjs/<symbol>")
def chart(symbol):
    interval = "1d"  # default interval for initial load
    ohlc, _ = get_stock_ohlc_data(symbol.upper(), interval)
    name = get_company_name(symbol.upper())

    return render_template(
        "chartjs.html",
        chart_title=f"{symbol.upper()} Stocks",
        ohlc_data=ohlc,
        symbol=symbol.upper(),
        name=name,
    )


@chart_bp.route("/lightweight/<symbol>")
def lightweight_chart(symbol):
    """Render chart using Lightweight Charts library."""
    interval = "1d"  # default interval for initial load
    ohlc, _ = get_stock_ohlc_data(symbol.upper(), interval)
    name = get_company_name(symbol.upper())

    return render_template(
        "lightweightchart.html",
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


@chart_bp.route('/get_ohlc_range')
def get_data_range():
    """Fetch OHLC data for a specific date range for viewport panning."""
    interval = request.args.get('interval', '1d')
    symbol = request.args.get('symbol', 'AAPL')
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    if not start_date or not end_date:
        return jsonify({'error': 'start and end parameters required'}), 400
    
    from datetime import datetime
    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if 'T' in start_date else datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if 'T' in end_date else datetime.fromisoformat(end_date)
    
    ohlc, _ = fetch_ohlc_data(symbol, interval, start_dt, end_dt)
    
    print(f'OHLC range data count: {len(ohlc)}');
    return jsonify({'ohlc': ohlc})
