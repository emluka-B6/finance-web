import server.llm as llm


def test_default_provider_is_lowercase(monkeypatch):
    # The default provider must resolve to a valid (lowercase) key so lookups
    # like get_llm_base_url() do not raise KeyError('DeepSeek').
    monkeypatch.setattr(llm, "_selected_provider", None)
    assert llm.get_llm_provider() == "deepseek"
    assert llm.get_llm_base_url() == "https://api.deepseek.com"


def test_provider_normalized_to_lowercase(monkeypatch):
    # A capitalized env value must not break the provider dict lookups.
    monkeypatch.setattr(llm, "_selected_provider", "DeepSeek")
    assert llm.get_llm_provider() == "deepseek"
    assert llm.get_llm_base_url() == "https://api.deepseek.com"


def _register_and_login(client):
    client.post("/register", data={"name": "alice", "email": "alice@gmail.com", "password": "pass123"})
    client.post("/login", data={"email": "alice@gmail.com", "password": "pass123"})


def test_settings_save_llm_provider_and_model(client, monkeypatch):
    monkeypatch.setattr(llm, "_selected_provider", None)
    monkeypatch.setattr(llm, "_selected_model", None)
    _register_and_login(client)

    response = client.post("/settings", data={
        "chart_provider": "chartjs",
        "llm_provider": "deepseek",
        "llm_model": "deepseek-v4-pro",
    })
    assert response.status_code == 302

    assert llm.get_llm_provider() == "deepseek"
    assert llm.get_llm_model() == "deepseek-v4-pro"
    # The base URL is derived from the selected provider.
    assert llm.get_llm_base_url() == "https://api.deepseek.com/v1"


def test_settings_reject_invalid_llm_model(client, monkeypatch):
    monkeypatch.setattr(llm, "_selected_provider", None)
    monkeypatch.setattr(llm, "_selected_model", None)
    _register_and_login(client)

    response = client.post("/settings", data={
        "chart_provider": "chartjs",
        "llm_provider": "openai",
        "llm_model": "not-a-real-model",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Unknown model" in response.data
    # The invalid selection must not be stored.
    assert llm.get_llm_provider() == "openai"
    assert llm.get_llm_model() != "not-a-real-model"


def test_settings_save_llm_api_key(client, monkeypatch):
    monkeypatch.setattr(llm, "_selected_api_key", None)
    _register_and_login(client)

    response = client.post("/settings", data={
        "chart_provider": "chartjs",
        "llm_provider": "openai",
        "llm_model": "gpt-4o",
        "llm_api_key": "sk-test-123",
    })
    assert response.status_code == 302

    assert llm.get_llm_api_key() == "sk-test-123"


def test_settings_blank_api_key_keeps_env_default(client, monkeypatch):
    monkeypatch.setattr(llm, "_selected_api_key", None)
    _register_and_login(client)

    client.post("/settings", data={
        "chart_provider": "chartjs",
        "llm_provider": "openai",
        "llm_model": "gpt-4o",
        "llm_api_key": "",
    })

    # A blank key must not override the environment default.
    assert llm.get_llm_api_key() == llm.LLM_API_KEY
