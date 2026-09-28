"""Write and read latency under a chosen consistency level, against a real
cluster. Run:

    python -m cassandra_ops_lab.loadtest.load_runner --n-events 500 --consistency LOCAL_QUORUM
"""

import argparse
import random
import statistics
import time

from cassandra import ConsistencyLevel

from cassandra_ops_lab.connection import get_session
from cassandra_ops_lab.events import SERVICES, generate_event
from cassandra_ops_lab.repository.deploy_history import get_recent_events_for_service, insert_deploy_event
from cassandra_ops_lab.schema.ddl import create_keyspace, create_tables

CONSISTENCY_LEVELS = {
    "ONE": ConsistencyLevel.ONE,
    "LOCAL_ONE": ConsistencyLevel.LOCAL_ONE,
    "LOCAL_QUORUM": ConsistencyLevel.LOCAL_QUORUM,
    "QUORUM": ConsistencyLevel.QUORUM,
    "ALL": ConsistencyLevel.ALL,
}


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, int(len(sorted_values) * pct))
    return sorted_values[index]


def run(contact_points: list[str], keyspace: str, n_events: int, consistency_name: str) -> dict:
    consistency = CONSISTENCY_LEVELS[consistency_name]
    session = get_session(contact_points)
    create_keyspace(session, keyspace, replication_factor=3)
    session.set_keyspace(keyspace)
    create_tables(session)
    time.sleep(3)  # let DDL propagate via gossip before writing (see docs/RUNBOOKS.md)

    rng = random.Random(7)
    write_latencies_ms = []
    for _ in range(n_events):
        event = generate_event(rng)
        start = time.perf_counter()
        insert_deploy_event(session, event, consistency_level=consistency)
        write_latencies_ms.append((time.perf_counter() - start) * 1000)

    read_latencies_ms = []
    for _ in range(50):
        start = time.perf_counter()
        get_recent_events_for_service(session, rng.choice(SERVICES), consistency_level=consistency)
        read_latencies_ms.append((time.perf_counter() - start) * 1000)

    return {
        "consistency_level": consistency_name,
        "n_events": n_events,
        "write_p50_ms": round(statistics.median(write_latencies_ms), 3),
        "write_p95_ms": round(percentile(write_latencies_ms, 0.95), 3),
        "write_p99_ms": round(percentile(write_latencies_ms, 0.99), 3),
        "read_p50_ms": round(statistics.median(read_latencies_ms), 3) if read_latencies_ms else None,
        "read_p95_ms": round(percentile(read_latencies_ms, 0.95), 3) if read_latencies_ms else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contact-points", nargs="+", default=["127.0.0.1"])
    parser.add_argument("--keyspace", default="cassandra_ops_lab")
    parser.add_argument("--n-events", type=int, default=500)
    parser.add_argument("--consistency", choices=list(CONSISTENCY_LEVELS), default="LOCAL_QUORUM")
    args = parser.parse_args()

    result = run(args.contact_points, args.keyspace, args.n_events, args.consistency)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
