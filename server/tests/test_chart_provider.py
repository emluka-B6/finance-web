from unittest.mock import patch


def test_selected_chart_uses_chartjs_by_default(client):
    response = client.get("/chart/AAPL")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/chartjs/AAPL")


def test_settings_save_selected_provider_and_chart_uses_it(client):
    client.post("/register", data={"name": "alice", "email": "alice@gmail.com", "password": "pass123"})
    client.post("/login", data={"email": "alice@gmail.com", "password": "pass123"})

    response = client.post("/settings", data={"chart_provider": "lightweight"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings")

    response = client.get("/chart/NVDA")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/lightweight/NVDA")

    response = client.get("/settings")
    assert b"value=\"lightweight\" checked" in response.data


def test_settings_require_login(client):
    response = client.get("/settings")

    assert response.status_code == 302
    assert "/login?next=%2Fsettings" in response.headers["Location"]


def test_invalid_chart_provider_is_not_saved(client):
    client.post("/register", data={"name": "alice", "email": "alice@gmail.com", "password": "pass123"})
    client.post("/login", data={"email": "alice@gmail.com", "password": "pass123"})
    response = client.post("/settings", data={"chart_provider": "unknown"}, follow_redirects=True)

    assert response.status_code == 200
    assert b"Please select a valid chart provider." in response.data
    assert b"value=\"chartjs\" checked" in response.data


def test_authenticated_navigation_shows_initial_avatar(client):
    client.post("/register", data={"name": "alice", "email": "alice@gmail.com", "password": "pass123"})
    client.post("/login", data={"email": "alice@gmail.com", "password": "pass123"})

    response = client.get("/news")

    assert b'href="/settings"' in response.data
    assert b'class="user-avatar ms-3"' in response.data
    assert b"\n                        A\n" in response.data


@patch("server.news.parse_company_feed", return_value=[])
@patch("server.news.parse_general_feed", return_value=[])
def test_news2_favorite_link_uses_selected_chart_route(mock_general_feed, mock_company_feed, client):
    with client.session_transaction() as sess:
        sess["guest_favorites"] = [{"symbol": "NVDA", "name": "NVIDIA"}]

    response = client.get("/news2")

    assert response.status_code == 200
    assert b'href="/chart/NVDA"' in response.data