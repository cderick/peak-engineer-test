"""Per-request timing.

Every response carries an X-Response-Time-Ms header and every request is logged
with how long it took. This is here so that "make it faster" is a measurement
rather than an opinion.

    scripts/bench.py      hit the dashboard forty times, print p50 and p95
"""

import logging
import time

logger = logging.getLogger("timing")


async def timing_middleware(request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
    logger.info("%s %s %.1fms", request.method, request.url.path, elapsed_ms)
    return response
