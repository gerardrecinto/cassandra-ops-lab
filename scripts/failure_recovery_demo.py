"""Real failure/recovery test against the 3-node local cluster: stop one
node, show QUORUM still works and ALL doesn't, restart the node, show ALL
works again. Run:

    python scripts/failure_recovery_demo.py

Requires the cluster from docker-compose.yml (`cassandra-ops-lab-cassandra-2-1`
is the node this script stops/restarts).
"""

import subprocess
import time
import uuid
from datetime import datetime, timezone

from cassandra import ConsistencyLevel, Unavailable

from cassandra_ops_lab.connection import get_session
from cassandra_ops_lab.repository.deploy_history import insert_deploy_event
from cassandra_ops_lab.schema.ddl import create_keyspace, create_tables

KEYSPACE = "cassandra_ops_lab_failure_demo"
TARGET_CONTAINER = "cassandra-ops-lab-cassandra-2-1"


def make_event(service: str) -> dict:
    return {
        "event_id": uuid.uuid4(),
        "service": service,
        "environment": "prod",
        "status": "succeeded",
        "released_by": "engineer-1",
        "occurred_at": datetime.now(timezone.utc),
        "duration_seconds": 90.0,
    }


def try_write(session, consistency, label: str) -> None:
    try:
        insert_deploy_event(session, make_event(f"service-failtest-{label}"), consistency_level=consistency)
        print(f"  {label}: WRITE SUCCEEDED at {consistency}")
    except Unavailable as exc:
        print(f"  {label}: WRITE FAILED at {consistency} -- Unavailable: {exc}")
    except Exception as exc:
        print(f"  {label}: WRITE FAILED at {consistency} -- {type(exc).__name__}: {exc}")


def docker(*args: str) -> None:
    subprocess.run(["docker", *args], check=True, capture_output=True)


def wait_for_node_count(session_host: str, expected_up: int, timeout_s: int = 90) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        result = subprocess.run(
            ["docker", "exec", "cassandra-ops-lab-cassandra-1-1", "nodetool", "status"],
            capture_output=True,
            text=True,
        )
        up_count = result.stdout.count("\nUN")
        if up_count >= expected_up:
            return
        time.sleep(3)
    raise TimeoutError(f"cluster did not reach {expected_up} UN nodes within {timeout_s}s")


def main() -> None:
    session = get_session(["127.0.0.1"])
    create_keyspace(session, KEYSPACE, replication_factor=3)
    session.set_keyspace(KEYSPACE)
    create_tables(session)
    time.sleep(3)  # let DDL propagate via gossip to all replicas before writing at ALL

    print("== all 3 nodes up ==")
    try_write(session, ConsistencyLevel.ALL, "baseline")
    try_write(session, ConsistencyLevel.QUORUM, "baseline")

    print(f"\n== stopping {TARGET_CONTAINER} ==")
    docker("stop", TARGET_CONTAINER)
    time.sleep(10)  # let the other nodes' failure detector notice

    print("== 1 of 3 nodes down ==")
    try_write(session, ConsistencyLevel.ALL, "degraded")  # expected to fail: needs 3/3
    try_write(session, ConsistencyLevel.QUORUM, "degraded")  # expected to succeed: needs 2/3, has 2/3
    try_write(session, ConsistencyLevel.ONE, "degraded")  # expected to succeed: needs 1/3

    print(f"\n== restarting {TARGET_CONTAINER} ==")
    docker("start", TARGET_CONTAINER)
    wait_for_node_count("127.0.0.1", expected_up=3)
    print("== all 3 nodes back up ==")
    try_write(session, ConsistencyLevel.ALL, "recovered")

    session.shutdown()


if __name__ == "__main__":
    main()
