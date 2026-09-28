"""Query-first schema design.

The queries this schema needs to answer, decided BEFORE any table was
written (Cassandra has no ad-hoc JOIN or secondary-index-free arbitrary
WHERE — the table shape IS the query plan):

  Q1: most recent N deploy events for a given service (default dashboard view)
  Q2: all deploy events for a given service on a specific day (incident investigation)
  Q3: most recent N deploy events for a given service, filtered to one environment
  Q4: how many deploys has a service had today (cheap aggregate, no COUNT(*) scan)

Three tables, one per access pattern, each denormalized rather than
joined — this is the normal Cassandra way, not a shortcut. There is no
single "deploy_events" table queried three different ways.

**Time bucketing** (the `day` component of every partition key): without
it, `(service)` alone as a partition key means one partition grows
forever for a long-lived, frequently-deployed service — a classic
Cassandra anti-pattern ("unbounded partition growth") that eventually
produces partitions too large to read efficiently or even to repair in a
reasonable time. Bucketing by day bounds partition size to "however many
deploys one service has in one day," which is a small, predictable number.

**TTL + TimeWindowCompactionStrategy**: `default_time_to_live` expires
rows after 90 days — this is time-series data; nobody queries a specific
deploy from a year ago through this table (an analytics/archive store
would be the right place for long-term history, not this table). Every
expired row leaves a tombstone. `SizeTieredCompactionStrategy` (the
default) compacts by file size, which for pure time-series TTL'd data
means old tombstones linger across compactions that never touch them
until an unrelated large compaction happens to include them —
`TimeWindowCompactionStrategy` (TWCS) instead compacts data within a
fixed time window together, so once every row in an entire time-window's
SSTable has expired, that whole SSTable can be dropped outright without
a compaction pass reading through it. TWCS is the standard recommended
choice specifically for TTL'd, monotonically-time-ordered write patterns
like this one — not a default, a fit to this exact shape of data.

**Counter table** (Q4): a `counter` column type increments atomically
without a read-before-write, avoiding both the cost and the race
condition of `SELECT count(*)` at scale (which in Cassandra is a full
partition scan, not an indexed count). Counter columns come with a real
constraint: a counter table can only contain the partition/clustering
keys and counter columns — no non-counter columns can be mixed in, and
counters cannot have a TTL — a lab-tested limitation, not a footnote (see
tests/test_ddl_constraints.py).
"""

KEYSPACE_DDL = """
CREATE KEYSPACE IF NOT EXISTS {keyspace}
WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': {replication_factor}}};
"""

DEPLOY_EVENTS_BY_SERVICE_DAY_DDL = """
CREATE TABLE IF NOT EXISTS deploy_events_by_service_day (
    service text,
    day text,
    occurred_at timestamp,
    event_id uuid,
    environment text,
    status text,
    released_by text,
    duration_seconds double,
    PRIMARY KEY ((service, day), occurred_at, event_id)
) WITH CLUSTERING ORDER BY (occurred_at DESC, event_id ASC)
  AND default_time_to_live = 7776000
  AND compaction = {'class': 'TimeWindowCompactionStrategy', 'compaction_window_unit': 'DAYS', 'compaction_window_size': 1};
"""

DEPLOY_EVENTS_BY_SERVICE_ENV_DAY_DDL = """
CREATE TABLE IF NOT EXISTS deploy_events_by_service_env_day (
    service text,
    environment text,
    day text,
    occurred_at timestamp,
    event_id uuid,
    status text,
    released_by text,
    duration_seconds double,
    PRIMARY KEY ((service, environment, day), occurred_at, event_id)
) WITH CLUSTERING ORDER BY (occurred_at DESC, event_id ASC)
  AND default_time_to_live = 7776000
  AND compaction = {'class': 'TimeWindowCompactionStrategy', 'compaction_window_unit': 'DAYS', 'compaction_window_size': 1};
"""

DEPLOY_COUNTS_BY_SERVICE_DAY_DDL = """
CREATE TABLE IF NOT EXISTS deploy_counts_by_service_day (
    service text,
    day text,
    deploy_count counter,
    PRIMARY KEY ((service, day))
);
"""


def create_keyspace(session, keyspace: str, replication_factor: int) -> None:
    session.execute(KEYSPACE_DDL.format(keyspace=keyspace, replication_factor=replication_factor))


def create_tables(session) -> None:
    session.execute(DEPLOY_EVENTS_BY_SERVICE_DAY_DDL)
    session.execute(DEPLOY_EVENTS_BY_SERVICE_ENV_DAY_DDL)
    session.execute(DEPLOY_COUNTS_BY_SERVICE_DAY_DDL)
