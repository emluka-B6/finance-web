
from unittest.mock import patch

def test_toggle_favorite_adds_symbol(client):
    """
    Test that toggling a new symbol adds it to the session favorites.
    """

    # Anonymous favourites use a dedicated guest session key.
    with client.session_transaction() as sess:
        sess["guest_favorites"] = []

    response = client.post("/toggle_favorite/AAPL?name=Apple")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "added"

    # Verify session contents
    with client.session_transaction() as sess:
        assert sess["guest_favorites"] == [{"symbol": "AAPL", "name": "Apple"}]


def test_toggle_favorite_removes_symbol(client):
    """
    Test that toggling an existing symbol removes it.
    """

    # Preload session with the symbol
    with client.session_transaction() as sess:
        sess["guest_favorites"] = [{"symbol": "AAPL", "name": "Apple"}]

    response = client.post("/toggle_favorite/AAPL")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "removed"

    # Verify removal
    with client.session_transaction() as sess:
        assert sess["guest_favorites"] == []


def test_authenticated_favorites_are_isolated_by_user(client):
    client.post("/register", data={"name": "alice", "email": "alice@gmail.com", "password": "pass123"})
    client.post("/register", data={"name": "bob", "email": "bob@gmail.com", "password": "pass123"})

    client.post("/login", data={"email": "alice@gmail.com", "password": "pass123"})
    client.post("/toggle_favorite/NVDA?name=NVIDIA")
    assert client.get("/get_favorites").get_json() == [{"symbol": "NVDA", "name": "NVIDIA"}]

    client.get("/logout")
    assert client.get("/get_favorites").get_json() == []

    client.post("/login", data={"email": "bob@gmail.com", "password": "pass123"})
    assert client.get("/get_favorites").get_json() == []

    client.post("/toggle_favorite/MSFT?name=Microsoft")
    client.get("/logout")
    client.post("/login", data={"email": "alice@gmail.com", "password": "pass123"})
    assert client.get("/get_favorites").get_json() == [{"symbol": "NVDA", "name": "NVIDIA"}]

@patch("server.favs.requests.get")
def test_search_ticker_success(mock_get, client):
    mock_get.return_value.ok = True
    mock_get.return_value.json.return_value = {
        "quotes": [
            {"symbol": "AAPL", "shortname": "Apple Inc.", "exchange": "NASDAQ"},
        ]
    }

    response = client.get("/search_ticker?q=aap")

    assert response.status_code == 200
    assert response.json == [
        {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"}
    ]

from unittest.mock import MagicMock

def test_search_ticker_success_with_magickmock(client):
    fake_json = {
        "quotes": [
            {"symbol": "AAPL", "shortname": "Apple Inc.", "exchange": "NASDAQ"},
            {"symbol": "MSFT", "shortname": "Microsoft Corp.", "exchange": "NASDAQ"},
        ]
    }

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = fake_json

    with patch("server.favs.requests.get", return_value=mock_resp):
        response = client.get("/search_ticker?q=app")

    assert response.status_code == 200
    assert response.json == [
        {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"},
        {"symbol": "MSFT", "name": "Microsoft Corp.", "exchange": "NASDAQ"},
    ]

def test_search_ticker_empty_query(client):
    response = client.get("/search_ticker?q=")
    assert response.status_code == 200
    assert response.json == []

def test_search_ticker_non_ok_response(client):
    mock_resp = MagicMock()
    mock_resp.ok = False

    with patch("server.favs.requests.get", return_value=mock_resp):
        response = client.get("/search_ticker?q=app")

    assert response.status_code == 500
    assert response.json == {"error": "No data"}

def test_search_ticker_exception(client):
    with patch("server.favs.requests.get", side_effect=Exception("Boom!")):
        response = client.get("/search_ticker?q=app")

    assert response.status_code == 500
    assert response.json == {"error": "Boom!"}


@patch("server.favs.request_yahoo_ticker")     # should NOT be called
@patch("server.favs.save_cache")               # should NOT be called
@patch("server.favs.load_cache")
def test_search_ticker_cache_hit(mock_load_cache, mock_save_cache, mock_yahoo, client):
    # Simulate that we already have cached results
    mock_load_cache.return_value = [
        {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"}
    ]

    response = client.get("/search_ttl_cache_ticker?q=aapl")

    # Response should come directly from cache
    assert response.status_code == 200
    assert response.json == mock_load_cache.return_value

    mock_yahoo.assert_not_called()
    mock_save_cache.assert_not_called()

@patch("server.favs.load_cache")
@patch("server.favs.save_cache")
@patch("server.favs.request_yahoo_ticker")
def test_search_cache_miss(mock_yahoo, mock_save_cache, mock_load_cache, client):
    mock_load_cache.return_value = []   # no cache
    mock_yahoo.return_value = (
        [{"symbol": "GOOG", "name": "Google", "exchange": "NASDAQ"}],
        ""    # state OK
    )

    response = client.get("/search_ttl_cache_ticker?q=goog")

    # Should return Yahoo result
    assert response.status_code == 200
    assert response.json == mock_yahoo.return_value[0]

    # Should call save_cache
    mock_save_cache.assert_called_once_with("goog", mock_yahoo.return_value[0])

@patch("server.favs.load_cache")
@patch("server.favs.save_cache")
@patch("server.favs.request_yahoo_ticker")
def test_search_cache_yahoo_error(mock_yahoo, mock_save_cache, mock_load_cache, client):
    mock_load_cache.return_value = []
    mock_yahoo.return_value = ([], "Timeout")

    response = client.get("/search_ttl_cache_ticker?q=goog")

    assert response.status_code == 500
    assert response.json == {"error": "Timeout"}

    mock_save_cache.assert_not_called()



from server.favs import format_time_str
from datetime import datetime, timezone

def test_format_time_str_int_timestamp(fixed_datetime):
    # not needed
    fixed_datetime.setDatetime(datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc), True)

    ts = datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc).timestamp()
    result = format_time_str(ts)

    assert result == "11:30" # depends on current zone hours offset ?

def test_format_time_str_datetime_naive():
    dt = datetime(2025, 1, 1, 8, 20)  # naive -> system local timezone assumed
    result = format_time_str(dt)
    assert result == "08:20"

def test_format_time_str_datetime_aware():
    dt = datetime(2025, 1, 1, 18, 55, tzinfo=timezone.utc)
    result = format_time_str(dt)
    assert result == "19:55"

def test_format_time_str_invalid(fixed_datetime):
    fixed_datetime.setDatetime(datetime(2025, 1, 1, 15, 37), False)
    result = format_time_str("not a date")
    assert result == "15:37"

def test_format_time_str_none(fixed_datetime):
    fixed_datetime.setDatetime(datetime(2025, 1, 1, 7, 15), False)
    result = format_time_str(None)
    assert result == "07:15"