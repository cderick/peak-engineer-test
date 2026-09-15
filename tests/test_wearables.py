"""Starting point for the task 2 tests.

These go through HTTP only and say nothing about how deliveries are stored;
that layout is yours to choose. The xfail below fails today because the endpoint
does not persist. Remove the marker once it does, then add tests for provider
differences, missing values, repeated deliveries and the history response.
"""

import json
from pathlib import Path

import pytest

from app.models import StoredWearableDay

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


def test_ingest_stores_a_delivery(client, store):
    response = client.post(
        "/api/users/user-1/wearables", json=delivery("user-1", "2026-08-31")
    )
    assert response.status_code == 200
    assert response.json()["data"]["stored"] is True
    day = store.get("wearables:user-1", "2026-08-31", StoredWearableDay)
    assert day is not None
    assert day.provider == "oura"
    assert day.resting_hr_bpm == 64
    assert day.steps == 17925
    assert day.sleep_efficiency_pct == 89


@pytest.mark.parametrize(
    ("user_id", "name", "resting_hr_bpm", "steps", "sleep_efficiency_pct"),
    [
        ("user-1", "2026-08-31", 64, 17925, 89),
        ("user-2", "2026-08-31", 63, None, 80.9),
        ("user-3", "2026-07-17", 64, 25980, 91.2),
        ("user-4", "2026-08-20", 54, 30645, None),
    ],
)
def test_ingest_normalizes_provider_metrics(
    client, store, user_id, name, resting_hr_bpm, steps, sleep_efficiency_pct
):
    response = client.post(
        f"/api/users/{user_id}/wearables", json=delivery(user_id, name)
    )
    assert response.status_code == 200
    calendar_date = delivery(user_id, name)["data"]["calendar_date"]
    day = store.get(f"wearables:{user_id}", calendar_date, StoredWearableDay)
    assert day is not None
    assert (day.resting_hr_bpm, day.steps, day.sleep_efficiency_pct) == (
        resting_hr_bpm,
        steps,
        sleep_efficiency_pct,
    )


def test_later_delivery_replaces_the_whole_normalized_day(client, store):
    for name in ("2026-07-17", "2026-07-17_r2"):
        assert (
            client.post(
                "/api/users/user-3/wearables", json=delivery("user-3", name)
            ).status_code
            == 200
        )

    day = store.get("wearables:user-3", "2026-07-17", StoredWearableDay)
    assert day is not None
    assert day.upload_id == "ga_20260717_r2"
    assert day.resting_hr_bpm == 67
    assert len(list(store.keys("wearables:user-3"))) == 1


def test_corrected_delivery_clears_a_missing_metric(client, store):
    first = delivery("user-1", "2026-08-31")
    first["data"]["activity_data"] = {"steps_samples": [{"value": 123}]}
    corrected = delivery("user-1", "2026-08-31")
    corrected["data"].pop("activity_data")

    for payload in (first, corrected):
        assert (
            client.post("/api/users/user-1/wearables", json=payload).status_code == 200
        )

    day = store.get("wearables:user-1", "2026-08-31", StoredWearableDay)
    assert day is not None
    assert day.steps is None


def test_ingest_ignores_malformed_or_null_step_samples(client, store):
    payload = delivery("user-1", "2026-08-31")
    payload["data"]["activity_data"] = {
        "steps_samples": [
            {"value": 100},
            {"value": 1.5},
            {"value": None},
            {},
            None,
            "not a sample",
            {"value": "200"},
            {"value": True},
        ]
    }

    response = client.post("/api/users/user-1/wearables", json=payload)
    assert response.status_code == 200
    day = store.get("wearables:user-1", "2026-08-31", StoredWearableDay)
    assert day is not None
    assert day.steps == 101.5


def test_home_returns_30_calendar_slots_with_missing_days_as_null(client):
    for name in ("2026-08-29", "2026-08-31"):
        assert (
            client.post(
                "/api/users/user-2/wearables", json=delivery("user-2", name)
            ).status_code
            == 200
        )
    response = sign_in(client, "user-2").get("/api/home")
    assert response.status_code == 200
    history = response.json()["data"]["wearable_history"]
    assert history["latest_date"] == "2026-08-31"
    assert len(history["days"]) == 30
    assert history["days"][0]["date"] == "2026-08-02"
    assert history["days"][-1]["date"] == "2026-08-31"
    assert history["days"][-2] == {
        "date": "2026-08-30",
        "resting_hr_bpm": None,
        "steps": None,
        "sleep_efficiency_pct": None,
    }
    assert history["days"][-1]["steps"] is None
