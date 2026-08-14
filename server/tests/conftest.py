import sys
import os

# Ensure project root (where app.py lives) is on sys.path
curr_dir = os.path.dirname(__file__)
up_dir = os.path.join(curr_dir, '..')
sys.path.insert(0, os.path.abspath(up_dir))

from misc.extensions import db
from app import create_app
import pytest
from cachelib import FileSystemCache

@pytest.fixture
def client():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_BINDS": {"sessions": "sqlite:///:memory:"}, #because ActivityLog has bind
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SESSION_TYPE": "cachelib",
        "SECRET_KEY": "test-secret-key",
        "SESSION_CACHELIB": FileSystemCache("./flask_session/.test-session"),
    })

    with app.app_context():
        db.create_all()

    with app.test_client() as client:
        yield client

    with app.app_context():
        db.session.remove()
        db.drop_all()



@pytest.fixture
def session_client(client):
    """
    Provides a helper to modify the session before making requests.
    Usage:
        session = session_client({"favorites": []})
        response = session.post("/toggle_favorite/AAPL")
    """
    def set_session(initial_data: dict):
        # Modify session before test
        with client.session_transaction() as sess:
            for k, v in initial_data.items():
                sess[k] = v

        return client  # return the same test client so you can run requests

    return set_session

from datetime import datetime, timezone

@pytest.fixture
def fixed_datetime(monkeypatch):
    # Patch datetime.now() to avoid local timezone randomness
    class FixedDatetime(datetime):
        fixed_now = datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc)
        useTz = False

        @classmethod
        def now(cls, tz=None):
            if cls.useTz:
                return cls.fixed_now if tz else cls.fixed_now.replace(tzinfo=None)
            else:
                return cls.fixed_now

        @classmethod
        def setDatetime(cls, datetime, useTz):
            cls.fixed_now = datetime
            cls.useTz = useTz

    monkeypatch.setattr("favs.datetime", FixedDatetime)
    return FixedDatetime
