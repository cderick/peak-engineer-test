from datetime import date, timedelta

from fastapi import APIRouter, Depends

from ..auth import current_user
from ..models import (
    BiomarkerDefinition,
    BiomarkerHistoryPoint,
    BiomarkerListPayload,
    BiomarkerView,
    Envelope,
    HomePayload,
    Member,
    ResultsDocument,
    StoredWearableDay,
    WearableHistory,
    WearableHistoryDay,
)
from ..store import Store, get_store

router = APIRouter(prefix="/api")


DEFINITIONS = "biomarker"


def definitions(store: Store) -> dict[str, BiomarkerDefinition]:
    return {
        marker_id: definition
        for marker_id, definition in store.query(DEFINITIONS, BiomarkerDefinition)
    }


def latest_results(
    store: Store, user_id: str
) -> tuple[list[BiomarkerView], str | None]:
    """Every measured biomarker, with its own chronological history."""
    partition = f"results:{user_id}"
    defs = definitions(store)
    histories: dict[str, list[BiomarkerHistoryPoint]] = {}
    latest: dict[str, tuple[BiomarkerHistoryPoint, BiomarkerDefinition | None]] = {}
    latest_draw: str | None = None

    for tested_at, draw in store.query(partition, ResultsDocument):
        latest_draw = tested_at
        for result in draw.results:
            point = BiomarkerHistoryPoint(
                tested_at=draw.tested_at,
                value=result.value,
                unit=result.unit,
                status=result.status,
                ranges=result.ranges,
            )
            histories.setdefault(result.biomarker_id, []).append(point)
            latest[result.biomarker_id] = (point, defs.get(result.biomarker_id))

    views = []
    for biomarker_id, (result, definition) in latest.items():
        views.append(
            BiomarkerView(
                biomarker_id=biomarker_id,
                name=definition.name if definition else biomarker_id,
                category=definition.category if definition else "other",
                description=definition.description if definition else "",
                direction=definition.direction if definition else "in_range",
                value=result.value,
                unit=result.unit,
                tested_at=result.tested_at,
                status=result.status,
                ranges=result.ranges,
                history=histories[biomarker_id],
            )
        )

    views.sort(key=lambda v: (v.category, v.name))
    return views, latest_draw


def latest_draw_results(
    store: Store, user_id: str
) -> tuple[list[BiomarkerView], str | None]:
    """The original latest-draw view used by the legacy biomarker endpoint."""
    partition = f"results:{user_id}"
    sort_keys = list(store.keys(partition))
    if not sort_keys:
        return [], None

    draw = store.get(partition, sort_keys[-1], ResultsDocument)
    if draw is None:
        return [], None

    defs = definitions(store)
    views = []
    for result in draw.results:
        definition = defs.get(result.biomarker_id)
        views.append(
            BiomarkerView(
                biomarker_id=result.biomarker_id,
                name=definition.name if definition else result.biomarker_id,
                category=definition.category if definition else "other",
                description=definition.description if definition else "",
                direction=definition.direction if definition else "in_range",
                value=result.value,
                unit=result.unit,
                tested_at=draw.tested_at,
                status=result.status,
                ranges=result.ranges,
            )
        )
    views.sort(key=lambda view: (view.category, view.name))
    return views, draw.tested_at


def wearable_history(store: Store, user_id: str) -> WearableHistory:
    partition = f"wearables:{user_id}"
    keys = list(store.keys(partition))
    if not keys:
        return WearableHistory()

    latest_date = date.fromisoformat(keys[-1])
    start_date = latest_date - timedelta(days=29)
    end_date = latest_date + timedelta(days=1)
    stored = {
        day.calendar_date: day
        for _key, day in store.query(
            partition,
            StoredWearableDay,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        )
    }
    days = []
    for offset in range(30):
        calendar_date = start_date + timedelta(days=offset)
        day = stored.get(calendar_date)
        days.append(
            WearableHistoryDay(
                date=calendar_date,
                resting_hr_bpm=day.resting_hr_bpm if day else None,
                steps=day.steps if day else None,
                sleep_efficiency_pct=day.sleep_efficiency_pct if day else None,
            )
        )
    return WearableHistory(latest_date=latest_date, days=days)


@router.get(
    "/biomarkers",
    response_model=Envelope[BiomarkerListPayload],
    response_model_exclude={"data": {"results": {"__all__": {"history"}}}},
)
def list_biomarkers(
    member: Member = Depends(current_user), store: Store = Depends(get_store)
):
    results, _tested_at = latest_draw_results(store, member.id)
    return Envelope(
        data=BiomarkerListPayload(results=results),
        meta={
            "count": len(results),
            "categories": sorted({r.category for r in results}),
        },
    )


@router.get("/home", response_model=Envelope[HomePayload])
def home(member: Member = Depends(current_user), store: Store = Depends(get_store)):
    """Everything the member's home screen needs, in one request.

    Budget: defined and measured by scripts/bench.py.
    Whatever you add to this screen, it has to still pass when you are done.
    """
    results, tested_at = latest_results(store, member.id)
    wearables = wearable_history(store, member.id)

    return Envelope(
        data=HomePayload(results=results, wearable_history=wearables),
        meta={
            "count": len(results),
            "categories": sorted({r.category for r in results}),
            "tested_at": tested_at,
        },
    )
