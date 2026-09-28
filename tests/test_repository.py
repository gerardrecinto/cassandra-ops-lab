from datetime import datetime, timezone

from cassandra_ops_lab.repository.deploy_history import (
    get_deploy_count,
    get_events_for_service_day,
    get_recent_events_for_service,
    get_recent_events_for_service_env,
    insert_deploy_event,
)


def make_event(**overrides) -> dict:
    import uuid

    event = {
        "event_id": uuid.uuid4(),
        "service": "service-01",
        "environment": "prod",
        "status": "succeeded",
        "released_by": "engineer-1",
        "occurred_at": datetime.now(timezone.utc),
        "duration_seconds": 120.5,
    }
    event.update(overrides)
    return event


def test_insert_and_query_by_service_day(clean_tables):
    session = clean_tables
    event = make_event()
    insert_deploy_event(session, event)

    day = event["occurred_at"].strftime("%Y-%m-%d")
    rows = get_events_for_service_day(session, "service-01", day)

    assert len(rows) == 1
    assert rows[0].event_id == event["event_id"]


def test_recent_events_limit_within_a_single_day(clean_tables):
    session = clean_tables
    for _ in range(5):
        insert_deploy_event(session, make_event(service="service-02"))

    rows = get_recent_events_for_service(session, "service-02", limit=3)
    assert len(rows) == 3


def test_recent_events_walks_back_across_multiple_day_partitions(clean_tables):
    from datetime import timedelta

    session = clean_tables
    today = datetime.now(timezone.utc)
    insert_deploy_event(session, make_event(service="service-05", occurred_at=today))
    insert_deploy_event(session, make_event(service="service-05", occurred_at=today - timedelta(days=1)))
    insert_deploy_event(session, make_event(service="service-05", occurred_at=today - timedelta(days=2)))

    # Each of these 3 events lives in a different day-bucketed partition --
    # this only returns all 3 if get_recent_events_for_service actually
    # walks backward across partitions rather than querying just today's.
    rows = get_recent_events_for_service(session, "service-05", limit=10, max_days_to_scan=5)
    assert len(rows) == 3


def test_recent_events_filtered_by_environment(clean_tables):
    session = clean_tables
    insert_deploy_event(session, make_event(service="service-03", environment="prod"))
    insert_deploy_event(session, make_event(service="service-03", environment="dev"))
    insert_deploy_event(session, make_event(service="service-03", environment="prod"))

    rows = get_recent_events_for_service_env(session, "service-03", "prod", limit=10)
    assert len(rows) == 2
    assert all(row.environment == "prod" for row in rows)


def test_deploy_count_increments(clean_tables):
    session = clean_tables
    event = make_event(service="service-04")
    day = event["occurred_at"].strftime("%Y-%m-%d")

    insert_deploy_event(session, event)
    insert_deploy_event(session, make_event(service="service-04", occurred_at=event["occurred_at"]))

    assert get_deploy_count(session, "service-04", day) == 2


def test_deploy_count_is_zero_for_unknown_service_day(clean_tables):
    session = clean_tables
    assert get_deploy_count(session, "service-nonexistent", "2020-01-01") == 0
