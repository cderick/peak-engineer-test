"""Starting point for the task 2 tests.

These go through HTTP only and say nothing about how deliveries are stored;
that layout is yours to choose. The xfail below fails today because the endpoint
does not persist. Remove the marker once it does, then add tests for provider
differences, missing values, repeated deliveries and the history response.
"""

import json
from pathlib import Path

import pytest

WEARABLES = Path(__file__).resolve().parents[1] / "data" / "wearables"

EMAILS = {
    "user-1": "james.chen@example.com",
    "user-2": "priya.raman@example.com",
    "user-3": "tom.okafor@example.com",
    "user-4": "sofia.marek@example.com",
}


def delivery(user_id, name):
    """One fixture file, e.g. delivery("user-3", "2026-07-17_r2")."""
    return json.loads((WEARABLES / user_id / f"{name}.json").read_text())


def sign_in(client, user_id):
    response = client.post("/api/auth/login", json={"email": EMAILS[user_id]})
    assert response.status_code == 200
    return client


@pytest.mark.xfail(strict=True, reason="task 2: persistence not implemented")
def test_ingest_stores_a_delivery(client):
    response = client.post(
        "/api/users/user-1/wearables", json=delivery("user-1", "2026-08-31")
    )
    assert response.status_code == 200
    assert response.json()["data"]["stored"] is True


def test_home_after_ingest(client):
    client.post("/api/users/user-1/wearables", json=delivery("user-1", "2026-08-31"))
    response = sign_in(client, "user-1").get("/api/home")
    assert response.status_code == 200
    assert set(response.json()) == {"data", "meta"}
