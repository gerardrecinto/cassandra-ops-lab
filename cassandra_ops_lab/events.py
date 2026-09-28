"""Synthetic deploy-event generator, self-contained in this repo (not
shared with the sibling kafka-ops-lab project — each portfolio repo is
independently runnable)."""

import random
import uuid
from datetime import datetime, timezone

SERVICES = [f"service-{i:02d}" for i in range(10)]
ENVIRONMENTS = ["dev", "staging", "prod"]
STATUSES = ["succeeded", "succeeded", "succeeded", "failed", "rolled_back"]


def generate_event(rng: random.Random, occurred_at: datetime | None = None) -> dict:
    return {
        "event_id": uuid.uuid4(),
        "service": rng.choice(SERVICES),
        "environment": rng.choice(ENVIRONMENTS),
        "status": rng.choice(STATUSES),
        "released_by": f"engineer-{rng.randint(1, 15)}",
        "occurred_at": occurred_at or datetime.now(timezone.utc),
        "duration_seconds": round(rng.uniform(30, 600), 2),
    }
