"""GET/PUT /api/settings (AC-01, AC-02)."""


def test_get_settings_returns_seed(client):
    res = client.get("/api/settings")
    assert res.status_code == 200
    body = res.json()
    assert body["business_name"] == "Daily Grind Cafe"
    assert body["brand_voice"] == "warm, welcoming, and slightly playful"


def test_get_settings_empty_store_returns_null(empty_client):
    res = empty_client.get("/api/settings")
    assert res.status_code == 200
    assert res.json() is None


def test_save_settings_persists_and_reads_back(client):
    payload = {
        "business_name": "Turbo Tacos",
        "business_type": "Restaurant",
        "description": "Late-night taco truck with vegan options.",
        "brand_voice": "bold and punchy",
    }
    res = client.put("/api/settings", json=payload)
    assert res.status_code == 200
    assert res.json() == payload
    assert client.get("/api/settings").json() == payload


def test_save_settings_validation_error(client):
    res = client.put(
        "/api/settings",
        json={"business_name": "", "business_type": "x", "description": "ok", "brand_voice": "y"},
    )
    assert res.status_code == 422
