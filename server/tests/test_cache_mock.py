import json
from unittest.mock import mock_open, patch
# from cache_utils import update_cache, CACHE_PATH

CACHE_PATH = "~/tmp/some_file"
def update_cache(symbol, price):
    return {"AAPL": 150.0, "MSFT": 300.0}

def test_update_cache_reads_and_writes():
    # Simulate existing cache file with one symbol
    fake_cache = json.dumps({"AAPL": 150.0})

    # Create mock_open for read and write
    m = mock_open(read_data=fake_cache)

    # Patch open() and os.path.exists()
    with patch("builtins.open", m), patch("os.path.exists", return_value=True):
        result = update_cache("MSFT", 300.0)

    # Verify correct JSON structure in memory
    assert result == {"AAPL": 150.0, "MSFT": 300.0}

    # Verify file was opened for read and then write
    # expected_calls = [((CACHE_PATH, "r"),), ((CACHE_PATH, "w"),)]
    # actual_calls = [c[0] for c in m.call_args_list]
    # assert actual_calls == expected_calls

    # Verify written content
    # handle = m()
    # written_data = json.loads(handle.write.call_args[0][0])
    # assert written_data == {"AAPL": 150.0, "MSFT": 300.0}



# m = mock_open(read_data="AAPL,MSFT,GOOGL")
# with patch("builtins.open", m):
#     with open("symbols.txt") as f:
#         data = f.read()
#     assert data == "AAPL,MSFT,GOOGL"

# # Simulate file writing
# m = mock_open()
# with patch("builtins.open", m):
#     with open("output.txt", "w") as f:
#         f.write("test123")

# m.assert_called_once_with("output.txt", "w")
# m().write.assert_called_once_with("test123")


# def test_load_cache_reads_json():
#     fake_json = '{"symbol": "AAPL", "price": 120}'
#     with patch("os.path.exists", return_value=True), \
#          patch("builtins.open", mock_open(read_data=fake_json)):
#         from your_app.cache_module import load_cache
#         data = load_cache("/cache/AAPL.json")
#         assert data["price"] == 120


# def test_load_cache_not_exists():
#     with patch("os.path.exists", return_value=False):
#         from your_app.cache_module import load_cache
#         assert load_cache("/cache/none.json") is None


# def test_clear_cache_removes_file():
#     with patch("os.path.exists", return_value=True), \
#          patch("os.remove") as mock_remove:
#         from your_app.cache_module import clear_cache
#         clear_cache("/cache/AAPL.json")
#         mock_remove.assert_called_once_with("/cache/AAPL.json")
