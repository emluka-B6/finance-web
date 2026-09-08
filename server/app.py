from flask import Flask, request
from flask_migrate import Migrate
from flask_session import Session
from dotenv import load_dotenv
import os

# Load .env into os.environ BEFORE importing any module that reads environment
# variables at import time (e.g. wig20.py binds LLM_API_KEY at module level).
load_dotenv()

from misc.extensions import db
from .favs import fav_bp
from .news import dashboard_bp
from .chart import chart_bp
from .table import table_bp, get_company_short_name
from .session import stats_bp, log_activity, clean_old_logs
from .user import user_bp, login_manager
from .wig20 import get_wig20_tickers, start_wig20_scheduler

# FLASK_ENV=production REDIS_URL=redis://localhost:6379/0 python app.py
# FLASK_ENV=development python app.py
session = Session()

def create_app(config=None):
    app = Flask(__name__)

    # Default config
    # app.config.from_pyfile("config.py")
    # Test config override
    if config:
        app.config.update(config)

    # Init extensions
    db.init_app(app)

    session_type = app.config.get("SESSION_TYPE")
    if session_type in ("sqlalchemy", "filesystem", "cachelib", "redis", "memcached", "mongodb"):
        session.init_app(app)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(fav_bp)
    app.register_blueprint(chart_bp)
    app.register_blueprint(table_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(stats_bp)

    login_manager.init_app(app)

    @app.context_processor
    def inject_wig20_tickers():
        # Expose the current WIG20 constituents to all templates (e.g. the
        # Poland dropdown menu in base.html). The ticker list is cached on
        # disk and refreshed at most once a day; each entry also carries a
        # human-friendly short name resolved from Yahoo Finance.
        tickers = get_wig20_tickers()
        return {
            "wig20_tickers": [
                {"symbol": t, "name": get_company_short_name(t)} for t in tickers
            ]
        }

    return app


app_config = dict() 
app_config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sqlite_alchemy.db' #Main DB

# --- Flask-Session configuration ---
app_config['SESSION_PROTECTION'] = 'strong'
app_config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "dev_secret_key") # flash(), session
app_config["SESSION_PERMANENT"] = False         # optional, session clears when browser closes
app_config["SESSION_USE_SIGNER"] = True         # add extra signing for security
# app_config["SESSION_PERMANENT"] = True
# app_config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

# --- Separate session database ---
ENV = os.environ.get("FLASK_ENV", "development")
if ENV == "production" and os.environ.get("REDIS_URL"):
    app_config["SESSION_TYPE"] = "redis"
    app_config["SESSION_REDIS"] = os.environ["REDIS_URL"]
elif ENV == "development":
    app_config["SESSION_TYPE"] = "sqlalchemy"
    app_config['SESSION_SQLALCHEMY'] = db
    app_config['SQLALCHEMY_BINDS'] = {'sessions': f'sqlite:///session_data.db'}
    app_config['SESSION_SQLALCHEMY_TABLE'] = 'flask_sessions'
else:
    app_config["SESSION_TYPE"] = "filesystem"
    #No app yet created, should find the path in other way
    # app_config["SESSION_FILE_DIR"] = os.path.join(app.root_path, "flask_session")
    app_config["SESSION_FILE_THRESHOLD"] = 500      # max number of session files to store
    print("Session files stored in:", app_config["SESSION_FILE_DIR"])

app = create_app(app_config)

migrate = Migrate(app, db)  # Initialize Flask-Migrate with app and db

# pip install apscheduler
# from apscheduler.schedulers.background import BackgroundScheduler
# scheduler = BackgroundScheduler()
# scheduler.add_job(func=cleanup_old_logs, trigger='interval', days=1)
# scheduler.start()

@app.before_request
def log_user_activity():
    # Skip logging for static files or the logging route itself
    if request.endpoint in ('static', 'stats.activity', 'favs.toggle_favorite', 
                            'favs.favorite_data', 'favicon'):
        return
    log_activity(request.path, request.method)


print(f'Session type: {app_config["SESSION_TYPE"]}, env {ENV}')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # creates models in main_app.db

        # only prepare sessions DB if SQLAlchemy backend is enabled
        if app.config.get("SESSION_TYPE") == "sqlalchemy":
            session_engine = db.engines['sessions']
            db.metadata.create_all(bind=session_engine)
            clean_old_logs(30)

    # Start the WIG20 scheduler only in the real server process (not the debug
    # reloader's parent process, which would otherwise start a duplicate thread).
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        print("Starting WIG20 scheduler")
        start_wig20_scheduler()

    app.run(debug=True)