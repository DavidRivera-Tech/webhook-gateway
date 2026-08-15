"""Re-queues delayed retry jobs when their backoff is up.
Runs as its own process (Windows-friendly, avoids the forking error)."""
import time
from rq import Queue
from rq.scheduler import RQScheduler
from app.queue import redis_conn

if __name__ == "__main__":
    queue = Queue("deliveries", connection=redis_conn)
    scheduler = RQScheduler([queue], connection=redis_conn)
    scheduler.acquire_locks()
    print("Scheduler started — watching for retries to re-queue...")
    while True:
        scheduler.enqueue_scheduled_jobs()
        time.sleep(1)