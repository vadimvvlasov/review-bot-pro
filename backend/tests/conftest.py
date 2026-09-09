import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store import DbStore

MEMORY_URL = "sqlite:///:memory:"


@pytest.fixture()
def store() -> DbStore:
    return DbStore(database_url=MEMORY_URL, seed=True)


@pytest.fixture()
def client(store: DbStore) -> TestClient:
    return TestClient(create_app(store))


@pytest.fixture()
def empty_client() -> TestClient:
    """No seed data and no settings (covers 400/empty paths)."""
    return TestClient(create_app(DbStore(database_url=MEMORY_URL, seed=False)))
