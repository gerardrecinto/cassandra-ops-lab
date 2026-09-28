"""Repository layer, one function per query this schema was designed for
(see schema/ddl.py's module docstring for the query-first rationale).

**Cross-partition writes and batches**: `deploy_events_by_service_day` and
`deploy_events_by_service_env_day` are two denormalized copies of the same
logical event, in different partitions. A LOGGED `BatchStatement` writes
both atomically (all-or-nothing, at a real coordinator-overhead cost) —
the standard Cassandra technique for keeping denormalized copies
consistent with each other. The counter increment
(`deploy_counts_by_service_day`) is a SEPARATE call, not part of the
batch: Cassandra does not allow mixing counter and non-counter mutations
in one batch. This means the count can, in a narrow failure window
(process dies between the batch and the counter call), drift from the
actual number of rows — a real, named tradeoff, not an oversight. See
docs/ARCHITECTURE.md.
"""

from datetime import datetime, timedelta, timezone

from cassandra import ConsistencyLevel
from cassandra.query import BatchStatement, SimpleStatement


def _day_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def insert_deploy_event(session, event: dict, consistency_level=ConsistencyLevel.LOCAL_QUORUM) -> None:
    occurred_at: datetime = event["occurred_at"]
    day = _day_str(occurred_at)

    batch = BatchStatement(consistency_level=consistency_level)
    batch.add(
        SimpleStatement(
            "INSERT INTO deploy_events_by_service_day "
            "(service, day, occurred_at, event_id, environment, status, released_by, duration_seconds) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        ),
        (
            event["service"],
            day,
            occurred_at,
            event["event_id"],
            event["environment"],
            event["status"],
            event["released_by"],
            event["duration_seconds"],
        ),
    )
    batch.add(
        SimpleStatement(
            "INSERT INTO deploy_events_by_service_env_day "
            "(service, environment, day, occurred_at, event_id, status, released_by, duration_seconds) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        ),
        (
            event["service"],
            event["environment"],
            day,
            occurred_at,
            event["event_id"],
            event["status"],
            event["released_by"],
            event["duration_seconds"],
        ),
    )
    session.execute(batch)

    session.execute(
        SimpleStatement(
            "UPDATE deploy_counts_by_service_day SET deploy_count = deploy_count + 1 WHERE service = %s AND day = %s",
            consistency_level=consistency_level,
        ),
        (event["service"], day),
    )


def get_events_for_service_day(session, service: str, day: str, consistency_level=ConsistencyLevel.LOCAL_ONE):
    stmt = SimpleStatement(
        "SELECT * FROM deploy_events_by_service_day WHERE service = %s AND day = %s",
        consistency_level=consistency_level,
    )
    return list(session.execute(stmt, (service, day)))


def get_recent_events_for_service(
    session,
    service: str,
    limit: int = 20,
    max_days_to_scan: int = 7,
    consistency_level=ConsistencyLevel.LOCAL_ONE,
) -> list:
    """Time-bucketed partitions mean "most recent N" isn't a single query —
    walk backward day by day, accumulating rows, until either `limit` is
    reached or `max_days_to_scan` is exhausted. Each individual query is a
    single bounded partition read; this is a small, predictable number of
    sequential reads, not an unbounded scan."""
    results = []
    today = datetime.now(timezone.utc)
    for offset in range(max_days_to_scan):
        day = _day_str(today - timedelta(days=offset))
        stmt = SimpleStatement(
            "SELECT * FROM deploy_events_by_service_day WHERE service = %s AND day = %s LIMIT %s",
            consistency_level=consistency_level,
        )
        rows = list(session.execute(stmt, (service, day, limit - len(results))))
        results.extend(rows)
        if len(results) >= limit:
            break
    return results[:limit]


def get_recent_events_for_service_env(
    session,
    service: str,
    environment: str,
    limit: int = 20,
    max_days_to_scan: int = 7,
    consistency_level=ConsistencyLevel.LOCAL_ONE,
) -> list:
    results = []
    today = datetime.now(timezone.utc)
    for offset in range(max_days_to_scan):
        day = _day_str(today - timedelta(days=offset))
        stmt = SimpleStatement(
            "SELECT * FROM deploy_events_by_service_env_day WHERE service = %s AND environment = %s AND day = %s LIMIT %s",
            consistency_level=consistency_level,
        )
        rows = list(session.execute(stmt, (service, environment, day, limit - len(results))))
        results.extend(rows)
        if len(results) >= limit:
            break
    return results[:limit]


def get_deploy_count(session, service: str, day: str, consistency_level=ConsistencyLevel.LOCAL_ONE) -> int:
    stmt = SimpleStatement(
        "SELECT deploy_count FROM deploy_counts_by_service_day WHERE service = %s AND day = %s",
        consistency_level=consistency_level,
    )
    row = session.execute(stmt, (service, day)).one()
    return row.deploy_count if row else 0
