"""Test fixtures.

Every test runs against its own copy of dev.db, made fresh for that test. Nothing
a test writes reaches the committed database, so `scripts/test` never puts a binary
diff in your branch, and tests cannot affect each other through shared state.
"""

import shutil

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import DB_PATH, Store, get_store

MEMBER = "james.chen@example.com"


@pytest.fixture
def db_path(tmp_path):
    copy = tmp_path / "test.db"
    shutil.copy(DB_PATH, copy)
    return copy


@pytest.fixture
def store(db_path):
    store = Store(db_path)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture
def client(db_path):
    def override():
        store = Store(db_path)
        try:
            yield store
        finally:
            store.close()

    app.dependency_overrides[get_store] = override
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_store, None)


@pytest.fixture
def signed_in(client):
    response = client.post("/api/auth/login", json={"email": MEMBER})
    assert response.status_code == 200
    return client
