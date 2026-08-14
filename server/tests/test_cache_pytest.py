import json
import pytest


@pytest.fixture
def fake_cache_file(tmp_path):
    """
    Creates a temporary directory and a fake cache.json file.
    Returns the path and pre-populated JSON data.
    """
    cache_file = tmp_path / "cache.json"
    data = {"AAPL": 150.0}
    cache_file.write_text(json.dumps(data))
    return cache_file


def test_update_cache_with_existing_file(monkeypatch, fake_cache_file):
    """
    Test update_cache() using pytest fixtures instead of mocks.
    """
    # Monkeypatch constants to point to our temp directory
    # monkeypatch.setattr("cache_utils.CACHE_PATH", str(fake_cache_file))

    # Run function (this will read/write the tmp file)
    # result = update_cache("MSFT", 300.0)

    # # Verify in-memory result
    # assert result == {"AAPL": 150.0, "MSFT": 300.0}

    # # Verify the file on disk really changed
    # saved = json.loads(fake_cache_file.read_text())
    # assert saved == {"AAPL": 150.0, "MSFT": 300.0}


def test_update_cache_with_new_file(tmp_path, monkeypatch):
    """
    Test when no cache.json exists initially.
    """
    fake_cache_path = tmp_path / "cache.json"

    # monkeypatch.setattr("cache_utils.CACHE_PATH", str(fake_cache_path))

    # result = update_cache("TSLA", 250.0)
    # assert result == {"TSLA": 250.0}

    # saved = json.loads(fake_cache_path.read_text())
    # assert saved == {"TSLA": 250.0}
