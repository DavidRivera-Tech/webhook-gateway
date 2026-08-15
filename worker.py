"""Processes delivery jobs. Scheduler runs separately."""
from rq import SimpleWorker, Queue
from app.queue import redis_conn

if __name__ == "__main__":
    queue = Queue("deliveries", connection=redis_conn)
    worker = SimpleWorker([queue], connection=redis_conn)
    print("Worker started — waiting for delivery jobs...")
    worker.work()