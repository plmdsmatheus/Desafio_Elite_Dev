import json
import time
from collections.abc import Callable, Iterator
from typing import Any

POLL_INTERVAL_SECONDS = 2
HEARTBEAT_EVERY_SECONDS = 15


def stream_while_changed(
    get_snapshot: Callable[[], Any],
    interval: float = POLL_INTERVAL_SECONDS,
    heartbeat_every: float = HEARTBEAT_EVERY_SECONDS,
) -> Iterator[str]:
    """Server-Sent Events generator: re-reads `get_snapshot()` every `interval`
    seconds and only emits a `data:` event when the payload actually changed —
    push to the client, plain poll-and-diff against Postgres underneath (no
    Celery/Channels/pub-sub in this project; this keeps that same shape). A
    `: heartbeat` comment line every `heartbeat_every` seconds keeps the
    connection alive through proxies that close idle connections.

    The first payload is yielded before the first `sleep()` — callers that
    only need to prove the wiring works can read a single item off this
    generator without ever blocking on real time passing."""
    ticks_since_change = 0
    last_payload = None
    while True:
        payload = json.dumps(get_snapshot(), default=str)
        if payload != last_payload:
            yield f"data: {payload}\n\n"
            last_payload = payload
            ticks_since_change = 0
        else:
            ticks_since_change += 1
            if ticks_since_change * interval >= heartbeat_every:
                yield ": heartbeat\n\n"
                ticks_since_change = 0
        time.sleep(interval)
