import os

import redis
from dotenv import load_dotenv

load_dotenv()

redis_host = os.environ.get("REDIS_HOST")
redis_port = os.environ.get("REDIS_PORT")
redis_password = os.environ.get("REDIS_PASSWD")

if redis_host and redis_port and redis_password:
    try:
        r = redis.Redis(
            host=redis_host,
            port=int(redis_port),
            password=redis_password,
            socket_connect_timeout=2,
        )
        r.flushdb()
        print("✅ Redis cache cleared.")
    except Exception as e:
        print(f"⚠️ Failed to clear Redis cache: {e}")
else:
    print("Redis configuration missing.")
