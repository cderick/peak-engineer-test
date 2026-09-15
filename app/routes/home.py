from fastapi import APIRouter, Depends

from ..auth import current_user
from ..models import (
    BiomarkerDefinition,
    BiomarkerListPayload,
    BiomarkerView,
    Envelope,
    HomePayload,
    Member,
    ResultsDocument,
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
    """Every biomarker with this member's most recent value.

    One partition per member, one document per draw, sorted by ISO timestamp. So
    the last sort key in the partition is the latest draw.

    Note what this throws away. Every earlier draw is sitting in the same
    partition and nothing here looks at it.
    """
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

    views.sort(key=lambda v: (v.category, v.name))
    return views, draw.tested_at


@router.get("/biomarkers", response_model=Envelope[BiomarkerListPayload])
def list_biomarkers(
    member: Member = Depends(current_user), store: Store = Depends(get_store)
):
    results, _tested_at = latest_results(store, member.id)
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

    return Envelope(
        data=HomePayload(results=results),
        meta={
            "count": len(results),
            "categories": sorted({r.category for r in results}),
            "tested_at": tested_at,
        },
    )
