#!/usr/bin/env -S uv run --script
"""Measure the member dashboard.

    scripts/bench.py                        40 serial requests
    scripts/bench.py --concurrency 8        8 at a time
    scripts/bench.py --path /api/biomarkers --n 50

Start the server first (`scripts/dev`). The budget is 35ms at p95, serial.

Serial numbers tell you whether the work per request is too big. Concurrent
numbers tell you whether requests are getting in each other's way, which is a
different problem with different causes — shared connections, blocking calls on
the event loop, lock contention. A change can improve one and ruin the other, so
look at both.
"""

import argparse
import http.cookiejar
import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BUDGET_MS = 35
MEMBER = "james.chen@example.com"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def sign_in(base: str, email: str):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    request = urllib.request.Request(
        f"{base}/api/auth/login",
        data=json.dumps({"email": email}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        opener.open(request).read()
    except Exception as err:
        raise SystemExit(f"could not sign in ({err}). Is the server running?") from err
    return opener


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--path", default="/api/home")
    parser.add_argument("--n", type=int, default=40)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--email", default=MEMBER)
    args = parser.parse_args()
    if args.n < 2 or args.concurrency < 1:
        parser.error("--n must be at least 2 and --concurrency at least 1")

    opener = sign_in(args.base, args.email)
    url = f"{args.base}{args.path}"
    body_bytes = 0

    def one():
        nonlocal body_bytes
        started = time.perf_counter()
        with opener.open(url) as response:
            body_bytes = len(response.read())
        return (time.perf_counter() - started) * 1000

    # Warm the process so the first request's import and page-cache cost does
    # not land in the numbers.
    one()

    wall = time.perf_counter()
    if args.concurrency > 1:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            timings = list(pool.map(lambda _: one(), range(args.n)))
    else:
        timings = [one() for _ in range(args.n)]
    wall = time.perf_counter() - wall

    timings.sort()
    p50 = statistics.median(timings)
    p95 = percentile(timings, 0.95)

    print(f"{args.path}  n={args.n}  concurrency={args.concurrency}")
    print(f"  p50    {p50:8.1f} ms")
    print(f"  p95    {p95:8.1f} ms   budget {BUDGET_MS} ms")
    print(f"  min    {timings[0]:8.1f} ms")
    print(f"  max    {timings[-1]:8.1f} ms")
    print(f"  thru   {args.n / wall:8.1f} req/s")
    print(f"  body   {body_bytes / 1024:8.1f} KB")
    print()
    if args.concurrency == 1 and args.path == "/api/home":
        print("  PASS" if p95 <= BUDGET_MS else "  OVER BUDGET")
        raise SystemExit(0 if p95 <= BUDGET_MS else 1)


if __name__ == "__main__":
    main()
