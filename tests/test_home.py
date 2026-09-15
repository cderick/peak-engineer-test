import pytest

from app.models import BiomarkerDefinition, BiomarkerResult, Ranges, ResultsDocument


@pytest.fixture
def home_data(store):
    for key in list(store.keys("results:user-1")):
        store.delete("results:user-1", key)
    ranges = Ranges(
        optimal={"min": 10, "max": 20},
        good={"min": 5, "max": 25},
        improve={"min": 0, "max": 30},
    )
    for marker_id, name, category in (
        ("a", "Zinc", "minerals"),
        ("b", "Copper", "minerals"),
        ("c", "Albumin", "liver"),
    ):
        store.put(
            "biomarker",
            marker_id,
            BiomarkerDefinition(
                id=marker_id,
                name=name,
                category=category,
                unit="mg/L",
                direction="in_range",
                description=f"About {name}",
                ranges=ranges,
            ),
        )

    def add_draw(user_id, tested_at, value):
        store.put(
            f"results:{user_id}",
            tested_at,
            ResultsDocument(
                user_id=user_id,
                tested_at=tested_at,
                results=[
                    BiomarkerResult(
                        biomarker_id=marker_id,
                        value=value,
                        unit="mg/L",
                        status="good",
                        ranges=ranges,
                    )
                    for marker_id in ("a", "b", "c")
                ],
            ),
        )

    return add_draw


@pytest.mark.parametrize("session", [None, "missing-member"])
def test_home_requires_a_valid_session(client, session):
    if session is not None:
        client.cookies.set("peak_session", session)
    assert client.get("/api/home").status_code == 401


def test_home_without_draws(signed_in, home_data):
    response = signed_in.get("/api/home")
    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "results": [],
            "wearable_history": {"latest_date": None, "days": []},
        },
        "meta": {"count": 0, "categories": [], "tested_at": None},
    }


def test_home_returns_latest_draw_with_definitions_and_stored_ranges(
    signed_in,
    store,
    home_data,
):
    home_data("user-1", "2026-09-10T09:00:00", 22)
    home_data("user-1", "2026-09-01T09:00:00", 12)
    definition = store.get("biomarker", "a", BiomarkerDefinition)
    assert definition is not None
    definition.ranges.optimal.max = 24
    store.put("biomarker", "a", definition)

    response = signed_in.get("/api/home")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {
        "count": 3,
        "categories": ["liver", "minerals"],
        "tested_at": "2026-09-10T09:00:00",
    }
    results = body["data"]["results"]
    assert [r["name"] for r in results] == ["Albumin", "Copper", "Zinc"]
    assert all(r["value"] == 22 for r in results)
    assert all(r["tested_at"] == "2026-09-10T09:00:00" for r in results)
    zinc = results[-1]
    assert zinc["biomarker_id"] == "a"
    assert zinc["category"] == "minerals"
    assert zinc["description"] == "About Zinc"
    assert zinc["unit"] == "mg/L"
    assert zinc["direction"] == "in_range"
    assert zinc["status"] == "good"
    assert zinc["ranges"]["optimal"] == {"min": 10, "max": 20}
    assert zinc["history"] == [
        {
            "tested_at": "2026-09-01T09:00:00",
            "value": 12.0,
            "unit": "mg/L",
            "status": "good",
            "ranges": {
                "optimal": {"min": 10.0, "max": 20.0},
                "good": {"min": 5.0, "max": 25.0},
                "improve": {"min": 0.0, "max": 30.0},
            },
        },
        {
            "tested_at": "2026-09-10T09:00:00",
            "value": 22.0,
            "unit": "mg/L",
            "status": "good",
            "ranges": {
                "optimal": {"min": 10.0, "max": 20.0},
                "good": {"min": 5.0, "max": 25.0},
                "improve": {"min": 0.0, "max": 30.0},
            },
        },
    ]


def test_home_keeps_a_biomarker_from_an_older_partial_draw(signed_in, store, home_data):
    home_data("user-1", "2026-09-01T09:00:00", 12)
    home_data("user-1", "2026-09-10T09:00:00", 22)
    latest = store.get("results:user-1", "2026-09-10T09:00:00", ResultsDocument)
    assert latest is not None
    latest.results = latest.results[:1]
    store.put("results:user-1", latest.tested_at, latest)

    results = signed_in.get("/api/home").json()["data"]["results"]
    by_id = {result["biomarker_id"]: result for result in results}
    assert by_id["a"]["tested_at"] == "2026-09-10T09:00:00"
    assert by_id["b"]["tested_at"] == "2026-09-01T09:00:00"
    assert by_id["c"]["tested_at"] == "2026-09-01T09:00:00"


def test_home_only_returns_the_signed_in_members_results(client, home_data):
    home_data("user-1", "2026-09-10T09:00:00", 12)
    home_data("user-2", "2026-09-11T09:00:00", 24)
    for email, value in (
        ("james.chen@example.com", 12),
        ("priya.raman@example.com", 24),
    ):
        assert client.post("/api/auth/login", json={"email": email}).status_code == 200
        response = client.get("/api/home")
        assert response.status_code == 200
        results = response.json()["data"]["results"]
        by_id = {result["biomarker_id"]: result for result in results}
        assert {"a", "b", "c"} <= by_id.keys()
        assert all(by_id[marker_id]["value"] == value for marker_id in ("a", "b", "c"))
