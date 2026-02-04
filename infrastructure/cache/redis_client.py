"""Redis cache client."""

import redis
import json


class RedisClient:
    """Redis client for caching and pub/sub."""

    def __init__(self, redis_url: str):
        self.client = redis.from_url(redis_url)

    def set_deployment_status(self, deployment_id: str, status: str):
        """Set deployment status in cache."""
        self.client.set(f"deployment:{deployment_id}:status", status)

    def get_deployment_status(self, deployment_id: str) -> str:
        """Get deployment status from cache."""
        status = self.client.get(f"deployment:{deployment_id}:status")
        return status.decode() if status else None

    def publish_event(self, channel: str, message: dict):
        """Publish event to Redis channel."""
        self.client.publish(channel, json.dumps(message))
