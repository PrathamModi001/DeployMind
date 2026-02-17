"""Redis cache client with pub/sub support for real-time events."""

import redis
import json
from typing import Callable, Optional
import threading


class RedisClient:
    """Redis client for caching and pub/sub.

    Supports:
    - Deployment status tracking
    - Event publishing to channels
    - Event subscription with callbacks
    - Real-time progress monitoring
    """

    def __init__(self, redis_url: str):
        """Initialize Redis client.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379)
        """
        self.client = redis.from_url(redis_url)
        self.pubsub = self.client.pubsub()
        self._subscription_thread: Optional[threading.Thread] = None

    def set_deployment_status(self, deployment_id: str, status: str):
        """Set deployment status in cache.

        Args:
            deployment_id: Unique deployment identifier
            status: Status string (pending, in_progress, completed, failed)
        """
        self.client.set(f"deployment:{deployment_id}:status", status)
        self.client.expire(f"deployment:{deployment_id}:status", 86400)  # 24 hours

    def get_deployment_status(self, deployment_id: str) -> Optional[str]:
        """Get deployment status from cache.

        Args:
            deployment_id: Unique deployment identifier

        Returns:
            Status string or None if not found
        """
        status = self.client.get(f"deployment:{deployment_id}:status")
        return status.decode() if status else None

    def set_deployment_data(self, deployment_id: str, key: str, value: str):
        """Set arbitrary deployment data in cache.

        Args:
            deployment_id: Unique deployment identifier
            key: Data key (e.g., 'image_tag', 'commit_sha')
            value: Data value
        """
        self.client.set(f"deployment:{deployment_id}:{key}", value)
        self.client.expire(f"deployment:{deployment_id}:{key}", 86400)

    def get_deployment_data(self, deployment_id: str, key: str) -> Optional[str]:
        """Get deployment data from cache.

        Args:
            deployment_id: Unique deployment identifier
            key: Data key

        Returns:
            Data value or None if not found
        """
        data = self.client.get(f"deployment:{deployment_id}:{key}")
        return data.decode() if data else None

    def publish_event(self, channel: str, message: dict):
        """Publish event to Redis channel.

        Args:
            channel: Channel name (e.g., 'deploymind:events')
            message: Event data dictionary (will be JSON-encoded)
        """
        self.client.publish(channel, json.dumps(message))

    def subscribe(self, channel: str, callback: Callable[[dict], None]):
        """Subscribe to a Redis channel and execute callback for each message.

        Args:
            channel: Channel name to subscribe to
            callback: Function to call with each message (receives dict)

        Example:
            def on_event(event: dict):
                print(f"Event: {event['event_type']}")

            redis_client.subscribe("deploymind:events", on_event)
        """
        self.pubsub.subscribe(channel)

        def listen():
            for message in self.pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        callback(data)
                    except json.JSONDecodeError:
                        # Skip invalid JSON
                        pass

        # Run listener in background thread
        self._subscription_thread = threading.Thread(target=listen, daemon=True)
        self._subscription_thread.start()

    def unsubscribe(self, channel: str):
        """Unsubscribe from a Redis channel.

        Args:
            channel: Channel name to unsubscribe from
        """
        self.pubsub.unsubscribe(channel)

    def close(self):
        """Close Redis connection and stop subscriptions."""
        if self._subscription_thread and self._subscription_thread.is_alive():
            self.pubsub.unsubscribe()
            self._subscription_thread.join(timeout=1)
        self.client.close()
