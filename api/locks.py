
import secrets

from redis.exceptions import RedisError

from api.redis_client import redis_client


RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


class ConversationLock:
    def __init__(self, lock_id: str, ttl=120):
        self.key = f"lock:conversation:{lock_id}"
        self.token = secrets.token_urlsafe(24)
        self.ttl = ttl
        self.acquired = False

    def acquire(self):
        self.acquired = bool(
            redis_client.set(
                self.key,
                self.token,
                nx=True,
                ex=self.ttl,
            )
        )
        return self.acquired

    def release(self):
        if self.acquired:
            redis_client.eval(
                RELEASE_SCRIPT,
                1,
                self.key,
                self.token,
            )
            self.acquired = False
