
import asyncio
import time
from collections import Counter

import httpx

URL = (
    "https://warranty-rag-frontend."
    "bravecoast-33edf5ab.centralindia.azurecontainerapps.io"
    "/api/v1/health"
)

DURATION_SECONDS = 90
CONCURRENT_WORKERS = 20


async def worker(client, stop_at, results):
    while time.monotonic() < stop_at:
        try:
            response = await client.get(URL)
            results[response.status_code] += 1
        except httpx.RequestError:
            results["ERROR"] += 1


async def main():
    results = Counter()
    start = time.monotonic()
    stop_at = start + DURATION_SECONDS

    limits = httpx.Limits(
        max_connections=CONCURRENT_WORKERS,
        max_keepalive_connections=CONCURRENT_WORKERS,
    )

    async with httpx.AsyncClient(
        timeout=10,
        limits=limits,
    ) as client:
        await asyncio.gather(
            *[
                worker(client, stop_at, results)
                for _ in range(CONCURRENT_WORKERS)
            ]
        )

    print("Duration:", round(time.monotonic() - start, 2))
    print("Results:", dict(results))
    print("Total requests:", sum(results.values()))


if __name__ == "__main__":
    asyncio.run(main())
