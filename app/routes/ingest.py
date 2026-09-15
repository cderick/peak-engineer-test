from fastapi import APIRouter, Depends, HTTPException

from ..models import (
    BiomarkerDefinition,
    BiomarkerResult,
    DrawBody,
    DrawPayload,
    DrawResultPayload,
    Envelope,
    Member,
    ResultsDocument,
    WearableBody,
    WearablePayload,
)
from ..store import Store, get_store

# Ingest is unauthenticated for this exercise. Production endpoints must
# authenticate the sender and authorize writes to the requested member.
router = APIRouter(prefix="/api/users/{user_id}")

DEFINITIONS = "biomarker"


def ingest_member(user_id: str, store: Store = Depends(get_store)) -> Member:
    member = store.get("user", user_id, Member)
    if member is None:
        raise HTTPException(status_code=404, detail="No such member")
    return member


@router.post("/wearables", response_model=Envelope[WearablePayload])
def add_wearable_day(body: WearableBody, member: Member = Depends(ingest_member)):
    """Receive one provider day. Persistence is part of task 2."""
    if body.member.reference_id != member.id:
        raise HTTPException(status_code=400, detail="Payload belongs to another member")
    return Envelope(data=WearablePayload(stored=False))


def band_for(value: float, definition: BiomarkerDefinition) -> str:
    """Which band a value falls into, per the marker's current definition."""
    for name in ("optimal", "good", "improve"):
        band = getattr(definition.ranges, name)
        if band.min <= value <= band.max:
            return name
    return "improve"


@router.post("/biomarkers/draws", response_model=Envelope[DrawPayload])
def add_draw(
    body: DrawBody,
    member: Member = Depends(ingest_member),
    store: Store = Depends(get_store),
):
    """Ingest a blood draw."""
    if not body.results:
        raise HTTPException(status_code=400, detail="A draw needs at least one result")

    problems: list[str] = []
    prepared: list[BiomarkerResult] = []

    for reading in body.results:
        definition = store.get(DEFINITIONS, reading.biomarker_id, BiomarkerDefinition)
        if definition is None:
            problems.append(f"{reading.biomarker_id}: no such biomarker")
            continue
        if reading.unit != definition.unit:
            problems.append(
                f"{reading.biomarker_id}: measured in {definition.unit},"
                f" got {reading.unit}"
            )
            continue

        prepared.append(
            BiomarkerResult(
                biomarker_id=reading.biomarker_id,
                value=reading.value,
                unit=reading.unit,
                status=band_for(reading.value, definition),
                ranges=definition.ranges,
                source="draw_import",
            )
        )

    if problems:
        raise HTTPException(status_code=400, detail=problems)

    partition = f"results:{member.id}"
    draw = store.get(partition, body.tested_at, ResultsDocument)
    created = draw is None

    if draw is None:
        draw = ResultsDocument(user_id=member.id, tested_at=body.tested_at, results=[])

    # Merge on biomarker id: a re-send of the same draw corrects it rather than
    # duplicating, and a partial re-send leaves everything else alone.
    incoming = {result.biomarker_id for result in prepared}
    draw.results = [r for r in draw.results if r.biomarker_id not in incoming]
    draw.results.extend(prepared)
    draw.results.sort(key=lambda r: r.biomarker_id)

    store.put(partition, body.tested_at, draw)

    return Envelope(
        data=DrawPayload(
            tested_at=draw.tested_at,
            created_draw=created,
            accepted=[
                DrawResultPayload(biomarker_id=r.biomarker_id, status=r.status)
                for r in prepared
            ],
            results_in_draw=len(draw.results),
        )
    )
