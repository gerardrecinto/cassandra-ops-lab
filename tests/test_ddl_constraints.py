"""Real, lab-verified Cassandra constraints -- not asserted from
documentation, actually triggered against the live cluster."""

import pytest
from cassandra.protocol import InvalidRequest


def test_counter_table_cannot_mix_non_counter_columns(session):
    with pytest.raises(InvalidRequest):
        session.execute(
            "CREATE TABLE IF NOT EXISTS bad_counter_table ("
            "service text, day text, deploy_count counter, released_by text, "
            "PRIMARY KEY ((service, day)))"
        )


def test_counter_column_cannot_have_ttl(session):
    session.execute(
        "CREATE TABLE IF NOT EXISTS ttl_counter_probe (service text PRIMARY KEY, hits counter)"
    )
    with pytest.raises(InvalidRequest):
        session.execute("UPDATE ttl_counter_probe USING TTL 60 SET hits = hits + 1 WHERE service = 'x'")


def test_keyspace_replication_factor_is_applied(session):
    from tests.conftest import TEST_KEYSPACE

    row = session.execute(
        "SELECT replication FROM system_schema.keyspaces WHERE keyspace_name = %s", (TEST_KEYSPACE,)
    ).one()
    assert row.replication["class"].endswith("SimpleStrategy")
    assert row.replication["replication_factor"] == "3"
