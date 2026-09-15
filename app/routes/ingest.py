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
    StoredWearableDay,
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
def add_wearable_day(
    body: WearableBody,
    member: Member = Depends(ingest_member),
    store: Store = Depends(get_store),
):
    """Normalize and replace one provider delivery for a member calendar day."""
    if body.member.reference_id != member.id:
        raise HTTPException(status_code=400, detail="Payload belongs to another member")

    day = normalize_wearable_day(body, member.id)
    store.put(f"wearables:{member.id}", day.calendar_date.isoformat(), day)
    return Envelope(data=WearablePayload(stored=True))


def normalize_wearable_day(body: WearableBody, user_id: str) -> StoredWearableDay:
    """Extract the three product metrics from a provider delivery.

    Oura, Garmin, and Fitbit expose step samples. Whoop supplies energy instead,
    which is deliberately not interpreted as steps.
    """
    data = body.data.model_dump()
    data.update(body.data.model_extra or {})

    if body.provider in {"oura", "garmin", "fitbit"}:
        heart_rate = data.get("heart_rate_data") or {}
        activity = data.get("activity_data") or {}
        sleep = data.get("sleep_data") or {}
        samples = activity.get("steps_samples")
        steps = None
        if isinstance(samples, list):
            steps = sum(
                sample["value"]
                for sample in samples
                if isinstance(sample, dict)
                and isinstance(sample.get("value"), (int, float))
                and not isinstance(sample["value"], bool)
            )
        return StoredWearableDay(
            user_id=user_id,
            calendar_date=body.data.calendar_date,
            upload_id=body.data.upload_id,
            provider=body.provider,
            resting_hr_bpm=heart_rate.get("resting_hr_bpm"),
            steps=steps,
            sleep_efficiency_pct=sleep.get("efficiency_pct"),
        )

    if body.provider == "whoop":
        heart_rate = data.get("heart_rate") or {}
        sleep = data.get("sleep") or {}
        efficiency = sleep.get("efficiency")
        return StoredWearableDay(
            user_id=user_id,
            calendar_date=body.data.calendar_date,
            upload_id=body.data.upload_id,
            provider=body.provider,
            resting_hr_bpm=(heart_rate.get("resting") or {}).get("bpm"),
            steps=None,
            sleep_efficiency_pct=(efficiency * 100 if efficiency is not None else None),
        )

    raise HTTPException(status_code=400, detail="Unsupported wearable provider")


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
