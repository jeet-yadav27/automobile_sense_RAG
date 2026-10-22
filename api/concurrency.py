
import asyncio

# Local development only:
# One inference operation at a time per API process.
rag_semaphore = asyncio.Semaphore(1)
