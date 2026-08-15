"""
Connects to Redis and creates the delivery job Queue.

Redis is the store that holds delivery jobs waiting to be processed.
RQ (Redis Queue) is the library that puts jobs on the queue (from the API)
and runs the worker that pulls them off.

The Redis host is read from the REDIS_HOST environment variable so the app
works both locally (127.0.0.1) and under Docker Compose (service name "redis").
"""

import os
from redis import Redis
from rq import Queue

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

redis_conn = Redis(host=REDIS_HOST, port=REDIS_PORT)
delivery_queue = Queue("deliveries", connection=redis_conn)
