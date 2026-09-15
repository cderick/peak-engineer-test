import pytest

from app.models import BiomarkerDefinition, ResultsDocument

URL = "/api/users/user-1/biomarkers/draws"
TESTED_AT = "2026-09-10T09:00:00"


@pytest.fixture
def definition(store):
    marker = BiomarkerDefinition(
        id="test_marker",
        name="Test marker",
        category="test",
        unit="mg/L",
        description="",
        direction="in_range",
        ranges={
            "optimal": {"min": 10, "max": 20},
            "good": {"min": 5, "max": 25},
            "improve": {"min": 0, "max": 30},
        },
    )
    store.put("biomarker", marker.id, marker)
    return marker


def reading(value=15):
    return {"biomarker_id": "test_marker", "value": value, "unit": "mg/L"}


def test_ingest_without_login_persists_to_path_member(client, store, definition):
    before = list(store.query("results:user-2"))
    response = client.post(URL, json={"tested_at": TESTED_AT, "results": [reading()]})
    assert response.status_code == 200
    assert response.json()["data"] == {
        "tested_at": TESTED_AT,
        "created_draw": True,
        "accepted": [{"biomarker_id": "test_marker", "status": "optimal"}],
        "results_in_draw": 1,
    }
    draw = store.get("results:user-1", TESTED_AT, ResultsDocument)
    assert draw is not None
    assert draw.user_id == "user-1"
    assert draw.tested_at == TESTED_AT
    assert len(draw.results) == 1
    assert draw.results[0].model_dump() == {
        **reading(),
        "status": "optimal",
        "ranges": definition.ranges.model_dump(),
        "source": "draw_import",
    }
    assert list(store.query("results:user-2")) == before


def test_partial_correction_preserves_other_results_and_retries_do_not_duplicate(
    client,
    store,
    definition,
):
    store.put("biomarker", "other", definition.model_copy(update={"id": "other"}))
    response = client.post(
        URL,
        json={
            "tested_at": TESTED_AT,
            "results": [reading(), {**reading(18), "biomarker_id": "other"}],
        },
    )
    assert response.status_code == 200
    correction = {"tested_at": TESTED_AT, "results": [reading(22)]}
    for _ in range(2):
        response = client.post(URL, json=correction)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["created_draw"] is False
        assert data["results_in_draw"] == 2
        assert data["accepted"] == [{"biomarker_id": "test_marker", "status": "good"}]
    draw = store.get("results:user-1", TESTED_AT, ResultsDocument)
    assert draw is not None
    assert len(draw.results) == 2
    assert {r.biomarker_id: r.value for r in draw.results} == {
        "test_marker": 22,
        "other": 18,
    }


@pytest.mark.parametrize(
    "value, status",
    [
        (0, "improve"),
        (5, "good"),
        (10, "optimal"),
        (20, "optimal"),
        (25, "good"),
        (30, "improve"),
        (31, "improve"),
    ],
)
def test_ingest_classifies_using_definition_ranges(
    client, store, definition, value, status
):
    response = client.post(
        URL, json={"tested_at": TESTED_AT, "results": [reading(value)]}
    )
    assert response.status_code == 200
    assert response.json()["data"]["accepted"][0]["status"] == status
    draw = store.get("results:user-1", TESTED_AT, ResultsDocument)
    assert draw is not None
    assert draw.results[0].status == status


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize(
    "invalid, expected_status",
    [
        ([], 400),
        ([reading(22), {**reading(), "biomarker_id": "missing"}], 400),
        ([reading(22), {**reading(), "unit": "wrong"}], 400),
        ([{**reading(), "value": "not-a-number"}], 422),
    ],
)
def test_invalid_draw_does_not_write_any_results(
    client,
    store,
    definition,
    existing,
    invalid,
    expected_status,
):
    if existing:
        assert (
            client.post(
                URL, json={"tested_at": TESTED_AT, "results": [reading()]}
            ).status_code
            == 200
        )
    before = list(store.scan())
    response = client.post(URL, json={"tested_at": TESTED_AT, "results": invalid})
    assert response.status_code == expected_status
    assert list(store.scan()) == before


def test_ingest_rejects_unknown_member_without_writing(client, store, definition):
    before = list(store.scan())
    response = client.post(
        "/api/users/missing/biomarkers/draws",
        json={"tested_at": TESTED_AT, "results": [reading()]},
    )
    assert response.status_code == 404
    assert list(store.scan()) == before
