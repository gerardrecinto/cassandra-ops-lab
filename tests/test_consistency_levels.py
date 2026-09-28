"""Real consistency-level behavior against the 3-node cluster with RF=3."""

from cassandra import ConsistencyLevel

from cassandra_ops_lab.repository.deploy_history import get_recent_events_for_service, insert_deploy_event
from tests.test_repository import make_event


def test_write_and_read_at_all_succeed_with_full_cluster_up(clean_tables):
    session = clean_tables
    event = make_event(service="service-cl-all")
    insert_deploy_event(session, event, consistency_level=ConsistencyLevel.ALL)

    rows = get_recent_events_for_service(session, "service-cl-all", consistency_level=ConsistencyLevel.ALL)
    assert len(rows) == 1


def test_write_and_read_at_quorum_succeed(clean_tables):
    session = clean_tables
    event = make_event(service="service-cl-quorum")
    insert_deploy_event(session, event, consistency_level=ConsistencyLevel.QUORUM)

    rows = get_recent_events_for_service(session, "service-cl-quorum", consistency_level=ConsistencyLevel.QUORUM)
    assert len(rows) == 1


def test_write_at_one_and_read_at_one_succeed(clean_tables):
    session = clean_tables
    event = make_event(service="service-cl-one")
    insert_deploy_event(session, event, consistency_level=ConsistencyLevel.ONE)

    rows = get_recent_events_for_service(session, "service-cl-one", consistency_level=ConsistencyLevel.ONE)
    assert len(rows) == 1
