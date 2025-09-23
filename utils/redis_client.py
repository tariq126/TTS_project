# utils/redis_client.py
import os
import redis

# Get the Redis URL from an environment variable, with a default for local dev
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create a reusable Redis client instance
redis_client = redis.from_url(REDIS_URL)