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

## Updating an existing installation

Pulling new application code does **not** apply database migrations automatically. Before starting a version that includes a new migration, stop the application and back up the database. For the default SQLite configuration, the database file is `server/instance/sqlite_alchemy.db`:

```bash
cp server/instance/sqlite_alchemy.db server/instance/sqlite_alchemy.db.backup
```

Apply all pending migrations from the `server` directory:

```bash
cd server
source ../venv/bin/activate
PYTHONPATH=".." flask --app app db upgrade
```

To confirm the installed migration version without changing the database, run:

```bash
PYTHONPATH=".." flask --app app db current
```

### Favourites upgrade

The user-scoped favourites update adds a `favorite` table. Existing user accounts and their other database data are preserved. Favourites created by the old version were stored only in the browser session under one shared key, with no owner information, so they cannot be safely assigned to a particular user during migration. After upgrading, each user should sign in and add their own favourites again. Any old shared session value is discarded on the next login or logout to prevent it being shown to another user.

## Testing an older revision safely

Use the worktree helper to test another revision without changing the current checkout or its development database. The tool creates a sibling worktree and makes an isolated, SQLite-consistent copy of `server/instance/sqlite_alchemy.db`; database migrations and destructive tests can then be run safely in that copy.

From the repository root:

```bash
python tools/create_test_worktree.py <revision> <worktree-name>
```

For example, to test the previous commit:

```bash
python tools/create_test_worktree.py HEAD~1 first_web_app-previous
cd ../first_web_app-previous
```

When finished, return to the original repository root and remove the worktree and its copied database:

```bash
python tools/remove_test_worktree.py first_web_app-previous
```

The creation tool refuses to overwrite an existing directory. Add `--no-database-copy` when a database copy is not needed. The removal tool refuses to delete a dirty worktree; use `python tools/remove_test_worktree.py --force first_web_app-previous` only when its uncommitted changes can be discarded. Run either tool with `--help` for all options.

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
| `LLM_API_KEY` | Empty (falls back to the hardcoded WIG20 list) | API key for the LLM used to look up the current WIG20 constituents. |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible base URL. Use `https://api.deepseek.com/v1` (DeepSeek) or `https://dashscope.aliyuncs.com/compatible-mode/v1` (Qwen) to switch providers. |
| `LLM_MODEL` | `gpt-4o-mini` | Model name for the LLM call (e.g. `deepseek-chat`, `qwen-plus`). |
| `LLM_USE_WEB_SEARCH` | `1` | When enabled, grounds the WIG20 lookup in live web results via the OpenAI Responses API web-search tool (OpenAI endpoint only; other providers fall back to a plain call). Set to `0` to disable. |
| `WIG20_DIAGNOSTICS_LOG` | `cache/wig20_diagnostics.jsonl` | Append-only log file (pretty-printed JSON, one record per lookup) where each lookup's status (model, source, cited/visited URLs, JSON errors, repeated tickers, count, format issues) is stored for later statistics. `visited_urls` holds the search sources after de-duplication by hostname and removal of clearly irrelevant domains; `cited_urls` holds only the URLs actually cited in the final answer. |
| `WIG20_REFRESH_ON_START` | `0` | When set to `1`/`true`, the scheduler performs an immediate warm-up refresh on startup. The scheduler also refreshes on startup if the cache is missing or stale (last refreshed on an earlier day). Disabled by default so server restarts during development don't trigger an LLM call unless the cache is actually missing/stale. |

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
