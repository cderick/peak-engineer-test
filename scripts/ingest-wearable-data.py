#!/usr/bin/env -S uv run --script
"""Send one member's wearable deliveries to the ingest API."""

import argparse
import json
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


def replay(user_id, base):
    files = sorted((DATA / "wearables" / user_id).glob("*.json"))
    if not files:
        raise SystemExit(f"No wearable fixtures for {user_id}")

    def post(path, body):
        request = urllib.request.Request(
            f"{base.rstrip('/')}{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    for path in files:
        post(f"/api/users/{user_id}/wearables", json.loads(path.read_text()))
    print(f"{user_id}: sent {len(files)} wearable payloads")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user", required=True, choices=("user-1", "user-2", "user-3", "user-4")
    )
    parser.add_argument("--base", default="http://localhost:8000")
    args = parser.parse_args()
    replay(args.user, args.base)


if __name__ == "__main__":
    main()
