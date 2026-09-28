"""Verified against the real cluster with a short TTL rather than waiting
90 days for the production default_time_to_live to actually expire
something."""

import time
import uuid
from datetime import datetime, timezone


def test_row_with_short_ttl_expires_and_disappears(session):
    event_id = uuid.uuid4()
    occurred_at = datetime.now(timezone.utc)
    day = occurred_at.strftime("%Y-%m-%d")

    session.execute(
        "INSERT INTO deploy_events_by_service_day "
        "(service, day, occurred_at, event_id, environment, status, released_by, duration_seconds) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) USING TTL 2",
        ("service-ttl-probe", day, occurred_at, event_id, "prod", "succeeded", "engineer-1", 10.0),
    )

    immediate = session.execute(
        "SELECT * FROM deploy_events_by_service_day WHERE service = %s AND day = %s",
        ("service-ttl-probe", day),
    ).one()
    assert immediate is not None

    time.sleep(3)

    after_expiry = session.execute(
        "SELECT * FROM deploy_events_by_service_day WHERE service = %s AND day = %s",
        ("service-ttl-probe", day),
    ).one()
    assert after_expiry is None
