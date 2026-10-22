
import os
from pathlib import Path

import redis
from dotenv import load_dotenv

load_dotenv(
    Path(__file__).resolve().parents[1] / ".env"
)

redis_client = redis.Redis.from_url(
    os.getenv(
        "REDIS_URL",
        "redis://localhost:6379/0",
    ),
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
    health_check_interval=30,
)
