
import asyncio
import httpx
import time

URL = (
    "https://warranty-rag-frontend."
    "bravecoast-33edf5ab.centralindia.azurecontainerapps.io"
    "/api/v1/health"
)

TOTAL_REQUESTS = 100
CONCURRENT_REQUESTS = 10


async def send_request(client, semaphore):
    async with semaphore:
        try:
            response = await client.get(URL)
            return response.status_code
        except httpx.RequestError:
            return "ERROR"


async def main():
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async with httpx.AsyncClient(timeout=15) as client:
        start = time.perf_counter()

        results = await asyncio.gather(
            *[
                send_request(client, semaphore)
                for _ in range(TOTAL_REQUESTS)
            ]
        )

        duration = time.perf_counter() - start

    print("Total requests:", len(results))
    print("Successful requests:", results.count(200))
    print("Failed requests:", len(results) - results.count(200))
    print("Duration:", round(duration, 2), "seconds")


asyncio.run(main())
