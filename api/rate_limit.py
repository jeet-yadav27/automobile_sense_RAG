
from fastapi import Depends, HTTPException
from redis.exceptions import RedisError

from api.dependencies import get_current_user
from api.redis_client import redis_client
from db.models import User


RATE_LIMIT = 10
WINDOW_SECONDS = 60

# Atomic INCR + EXPIRE in one Redis operation.
RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


def enforce_chat_rate_limit(
    user: User = Depends(get_current_user),
):
    key = f"rate:chat:{user.id}"

    try:
        count, ttl = redis_client.eval(
            RATE_LIMIT_SCRIPT,
            1,
            key,
            WINDOW_SECONDS,
        )
    except RedisError:
        # Fail closed if rate limiting is unavailable.
        raise HTTPException(
            status_code=503,
            detail="Rate limiter unavailable",
        )

    if count > RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many requests",
            headers={
                "Retry-After": str(max(1, ttl))
            },
        )
