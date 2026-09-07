import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store import InMemoryStore


@pytest.fixture()
def store() -> InMemoryStore:
    return InMemoryStore(seed=True)


@pytest.fixture()
def client(store: InMemoryStore) -> TestClient:
    return TestClient(create_app(store))


@pytest.fixture()
def empty_client() -> TestClient:
    """No seed data and no settings (covers 400/empty paths)."""
    return TestClient(create_app(InMemoryStore(seed=False)))
