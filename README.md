# Finance Web

A Flask-based finance dashboard for viewing market news, stock tables, interactive OHLC charts, and a session-backed list of favourite tickers. The application obtains market data and news from Yahoo Finance.

> **Disclaimer:** This project is for informational and educational use only. Market data may be delayed, incomplete, or unavailable; it is not investment advice.

## Features

- Yahoo Finance news feeds, including general and company-specific headlines
- Searchable ticker lookup and session-backed favourites
- Interactive Chart.js and Lightweight Charts views with selectable OHLC intervals
- On-demand historical OHLC data for chart navigation
- Snapshot tables for the WIG20 and the "Magnificent Seven" stocks
- User registration, login, roles, and an administrator-only user-management page
- Activity logging for authenticated users
- SQLite-backed application data and development sessions; Redis support for production sessions

## Technology

- Python and Flask
- Flask-SQLAlchemy, Flask-Migrate, Flask-Login, and Flask-Session
- SQLite for local development
- `yfinance`, pandas, and Yahoo Finance RSS/search endpoints for market data
- Chart.js and Lightweight Charts for browser-side charting

## Prerequisites

- Python 3.10 or newer
- Internet access to retrieve Yahoo Finance market data and news feeds

## Local setup

This repository does not currently include a dependency manifest. Create and activate a virtual environment, then install the packages imported by the application:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install Flask Flask-Login Flask-Migrate Flask-Session Flask-SQLAlchemy \
  email-validator feedparser pandas pytz yfinance pytest
```

Set a secret key before running the application. Generate a suitably random value for any non-local environment:

```bash
export SECRET_KEY="replace-with-a-long-random-secret"
```

## Run the application

From the repository root, start Flask as a module:

```bash
source .venv/bin/activate
FLASK_ENV=development python -m server.app
```

The development server listens at <http://127.0.0.1:5000>. On first launch, the application creates its SQLite tables automatically. Register an account at <http://127.0.0.1:5000/register>, then sign in at <http://127.0.0.1:5000/login>.

## Main routes

| Route | Description |
| --- | --- |
| `/news` | General and ticker-specific Yahoo Finance news dashboard |
| `/chartjs/<symbol>` | OHLC chart rendered with Chart.js, for example `/chartjs/AAPL` |
| `/lightweight/<symbol>` | OHLC chart rendered with Lightweight Charts |
| `/wig20` | WIG20 market table |
| `/mag7` | Magnificent Seven market table |
| `/register`, `/login`, `/logout` | Account registration and authentication |
| `/activity` | Authenticated user activity statistics |
| `/` | Administrator-only user-management page |

The chart and favourites interfaces also use JSON endpoints such as `/get_ohlc`, `/get_ohlc_range`, `/search_ticker`, `/get_favorites`, and `/toggle_favorite/<symbol>`.

## Configuration

| Variable | Development behavior | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | Falls back to `dev_secret_key` if unset | Signs Flask sessions and flash messages. Always set a strong value outside local development. |
| `FLASK_ENV` | Defaults to `development` | Selects the session backend. Development uses a SQLite-backed session store. |
| `REDIS_URL` | Not required in development | When `FLASK_ENV=production`, enables Redis-backed server-side sessions. Example: `redis://localhost:6379/0`. |

Application data is stored in SQLite. Local database, cache, and session files are intentionally ignored by Git.

## Tests

Run the complete test suite from the repository root:

```bash
source .venv/bin/activate
pytest
```

Tests are located in `server/tests` and use pytest fixtures and mocks to avoid relying on live external services where applicable.

## Project layout

```text
first_web_app/
├── server/
│   ├── app.py              # Flask application factory and configuration
│   ├── chart.py            # Chart pages and OHLC endpoints
│   ├── favs.py             # Ticker search and favourites endpoints
│   ├── news.py             # Yahoo Finance RSS news dashboard
│   ├── table.py            # WIG20 and Magnificent Seven tables
│   ├── user.py             # Authentication and user management
│   ├── templates/          # Jinja templates
│   └── tests/              # Pytest suite
├── misc/                   # SQLAlchemy models and extension setup
└── pytest.ini              # Pytest configuration
```

## Data-source note

Yahoo Finance endpoints and the `yfinance` library are third-party services. Their availability, returned symbols, rate limits, and data quality are outside this project’s control. Avoid making rapid repeated requests, and add appropriate caching, error handling, and provider-compliance checks before deploying this application for real users.

## Security note

The built-in Flask server runs with debug mode enabled and is appropriate only for local development. Before a production deployment, use a production WSGI server, configure Redis and a strong `SECRET_KEY`, disable debug mode, manage database migrations, and review authentication, authorization, rate limiting, and external-service failure handling.
