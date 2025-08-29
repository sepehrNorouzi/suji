import json
from celery import shared_task
import os
import redis
_redis = None

if os.getenv("IDEMPOTENCY_REDIS_URL"):
    _redis = redis.Redis.from_url(os.environ["IDEMPOTENCY_REDIS_URL"], decode_responses=True)

def _seen_event(event_id: str) -> bool:
    if _redis:
        return not _redis.set(name=f"evt:{event_id}", value="1", nx=True, ex=24*3600)

@shared_task(name="events.handle_game_started", acks_late=True)
def handle_game_started(raw_body: dict):
    if isinstance(raw_body, str):
        raw_body = json.loads(raw_body)

    event_id = raw_body.get("event_id")
    print(f"[handle_game_started] event raised with id {event_id}")
    if not event_id:
        raise ValueError("event_id missing")

    if _seen_event(event_id):
        return "duplicate"

    # ---- Your business logic here ----
    # e.g., record match start, notify users, etc.
    # Do DB writes inside transactions as needed.
    # ----------------------------------

    return "ok"

@shared_task
def test_event():
    print("Done")
    return {
        "done": True
    }
