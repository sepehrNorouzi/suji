import os
from celery import Celery, bootsteps
from kombu import Exchange, Queue, Consumer
from match.tasks import handle_game_started

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "suji.settings")
app = Celery("suji")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

GAME_EXCHANGE = Exchange("game.events", type="topic", durable=True)
GAME_QUEUE = Queue(
    "game.events.start",
    exchange=GAME_EXCHANGE,
    routing_key="game_started.*",
    durable=True,
    queue_arguments={
        "x-dead-letter-exchange": "game.events.dlx",
        "x-dead-letter-routing-key": "game-started.failed",
    },
)

task_queues = (
    Queue(
        "game.events.start",
        exchange=GAME_EXCHANGE,
        routing_key="game_started.*",
        durable=True,
        queue_arguments={
            "x-dead-letter-exchange": "game.events.dlx",
            "x-dead-letter-routing-key": "game-started.failed",
        },
    ),
    Queue(
        "game.events.dlq",
        exchange=Exchange("game.events.dlx", type="topic", durable=True),
        routing_key="game-started.failed",
        durable=True,
    ),
)
app.conf.task_queues = task_queues

app.conf.task_routes = {
    "events.handle_game_started": {
        "queue": "game.events.start",
        "routing_key": "game_started.global",
    }
}

app.conf.worker_prefetch_multiplier = 1  # process one message at a time per worker
app.conf.broker_heartbeat = 10


class GameEventsConsumer(bootsteps.ConsumerStep):
    def get_consumers(self, channel):
        return [Consumer(
            channel,
            queues=[GAME_QUEUE],
            accept=["json"],
            callbacks=[self.on_message],
        )]

    def on_message(self, body, message):
        # body is your event JSON dict
        handle_game_started.delay(body)
        message.ack()

app.steps["consumer"].add(GameEventsConsumer)
