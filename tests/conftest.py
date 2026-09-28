import pytest
from cassandra.cluster import NoHostAvailable

from cassandra_ops_lab.connection import get_session
from cassandra_ops_lab.schema.ddl import create_keyspace, create_tables

CONTACT_POINTS = ["127.0.0.1"]
TEST_KEYSPACE = "cassandra_ops_lab_test"


@pytest.fixture(scope="session")
def session():
    try:
        sess = get_session(CONTACT_POINTS)
    except NoHostAvailable:
        pytest.skip("local Cassandra cluster not reachable at 127.0.0.1:9042 (docker compose up -d)")
    create_keyspace(sess, TEST_KEYSPACE, replication_factor=3)
    sess.set_keyspace(TEST_KEYSPACE)
    create_tables(sess)
    yield sess
    sess.shutdown()


@pytest.fixture(autouse=False)
def clean_tables(session):
    session.execute("TRUNCATE deploy_events_by_service_day")
    session.execute("TRUNCATE deploy_events_by_service_env_day")
    session.execute("TRUNCATE deploy_counts_by_service_day")
    yield session
