#!/usr/bin/env -S uv run --script
"""Clear the store and load members, biomarker definitions and draws from JSON."""

import json
import sys
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import (  # noqa: E402
    BiomarkerDefinition,
    EmailPointer,
    Member,
    ResultsDocument,
)
from app.store import DB_PATH, Store  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"


def bootstrap(db_path: Path = DB_PATH) -> int:
    documents: list[tuple[str, str, BaseModel]] = []
    for value in json.loads((DATA / "members.json").read_text()):
        member = Member.model_validate(value)
        documents.append(("user", member.id, member))
        documents.append(("email", member.email, EmailPointer(user_id=member.id)))

    for value in json.loads((DATA / "biomarkers.json").read_text()):
        marker = BiomarkerDefinition.model_validate(value)
        documents.append(("biomarker", marker.id, marker))

    for path in sorted((DATA / "biomarkers").glob("*/*.json")):
        draw = ResultsDocument.model_validate_json(path.read_text())
        documents.append((f"results:{draw.user_id}", draw.tested_at, draw))

    store = Store(db_path)
    try:
        existing = [(pk, sk) for pk, sk, _ in store.scan()]
        for pk, sk in existing:
            store.delete(pk, sk)
        print(f"Cleared {len(existing)} documents from {db_path}")
        return store.put_many(documents)
    finally:
        store.close()


if __name__ == "__main__":
    print(f"Loaded {bootstrap()} documents into {DB_PATH}")
