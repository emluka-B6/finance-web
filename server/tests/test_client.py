
def test_news_page(client):
    resp = client.get("/news")
    assert resp.status_code == 200
    assert b"Register" in resp.data
    assert b"Login" in resp.data
    assert b"General Market News" in resp.data
    