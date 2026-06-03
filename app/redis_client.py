import redis
from app.config import settings

# decode_responses=True so all values come back as str, not bytes
client = redis.from_url(settings.redis_url, decode_responses=True)
