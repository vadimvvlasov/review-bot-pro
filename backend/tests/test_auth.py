"""Auth: hashed passwords, bearer tokens, and non-breaking spec access."""

from app.auth import hash_password, verify_password


def _register(client, username="owner", password="supersecret1"):
    return client.post("/api/auth/register", json={"username": username, "password": password})


def test_register_hashes_password(client, store):
    res = _register(client)
    assert res.status_code == 201
    assert res.json() == {"username": "owner"}
    stored = store.users["owner"].password_hash
    assert stored != "supersecret1"
    assert verify_password("supersecret1", stored)
    assert not verify_password("wrong", stored)


def test_register_duplicate_409(client):
    assert _register(client).status_code == 201
    res = _register(client)
    assert res.status_code == 409
    assert res.json() == {"message": "Username is already taken"}


def test_register_short_password_422(client):
    assert _register(client, password="short").status_code == 422


def test_login_returns_bearer_token(client):
    _register(client)
    res = client.post("/api/auth/login", data={"username": "owner", "password": "supersecret1"})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json() == {"username": "owner"}


def test_login_wrong_password_401(client):
    _register(client)
    res = client.post("/api/auth/login", data={"username": "owner", "password": "nope-nope-nope"})
    assert res.status_code == 401
    assert res.json() == {"message": "Incorrect username or password"}


def test_me_without_token_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_bad_token_401(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert res.status_code == 401


def test_spec_endpoints_work_with_and_without_token(client):
    _register(client)
    token = client.post(
        "/api/auth/login", data={"username": "owner", "password": "supersecret1"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/reviews").status_code == 200
    assert client.get("/api/reviews", headers=headers).status_code == 200
    assert client.get("/api/reviews", headers=headers).json() == client.get("/api/reviews").json()
    assert client.get("/api/settings", headers=headers).status_code == 200
