# Portfolio summary

## What this is

A Cassandra data-modeling portfolio project closing a genuine hands-on
gap: query-first schema design, time-bucketed partitions, TTL-aware
compaction strategy choice, consistency-level tradeoffs, and real
failure/recovery testing against a live 3-node cluster — including two
real operational incidents hit and fixed while building it, documented
as they actually happened, not smoothed over.

## Resume bullets (accurate language only)

- Built a query-first Cassandra schema (three denormalized tables, one
  per access pattern) with time-bucketed partition keys and
  TimeWindowCompactionStrategy for TTL'd time-series data.
- Diagnosed and resolved a real bootstrap token collision when
  concurrently starting multiple nodes in a fresh 3-node cluster.
- Verified consistency-level behavior (ONE/QUORUM/ALL) against actual
  node failure by stopping and restarting a live cluster node, not from
  documentation alone.
- Documented, with real numbers, why Cassandra fit this project's access
  pattern and where Postgres would be the better choice instead.

**Not used, and why**: "operated Cassandra in production," "managed a
production cluster" — I have no prior professional Cassandra experience;
this project demonstrates newly built hands-on capability, not
prior ownership.

## Interview talking points

**"Walk me through your data model."**
Four queries, decided first, drove three tables — no normalization, no
joins, each table denormalized for exactly the access pattern it serves.
The partition key in every table includes a `day` bucket specifically to
bound partition size, since a long-lived service's deploy history would
otherwise grow one partition forever.

**"What's a real problem you hit building this?"**
Two, both genuinely hit while building the lab, not staged. First: starting
two fresh nodes simultaneously caused a bootstrap token collision — fixed
by staggering node startup. Second: writing immediately after creating a
new table at strict consistency intermittently failed with
`INCOMPATIBLE_SCHEMA` because DDL hadn't finished propagating via gossip
to every node yet — fixed with a short settle delay after DDL. Both are
documented in the README exactly as they happened, including the actual
error text.

**"How do you know QUORUM actually tolerates a node failure?"**
I stopped one of three live nodes mid-script and watched `ALL` fail with
`Unavailable` while `QUORUM` and `ONE` kept succeeding —
`scripts/failure_recovery_demo.py`'s output is in the README verbatim,
not a description of expected behavior from documentation.

**"When would you NOT use Cassandra?"**
The moment a query needs an ad-hoc filter on a non-key column, a join
across entities, or a real multi-row transaction — see
`docs/CASSANDRA_VS_POSTGRES.md`. This project's sibling `kafka-ops-lab`
project deliberately uses Postgres for exactly that reason (idempotent
upserts need real transactional guarantees Cassandra's lightweight
transactions aren't built for at that granularity).

## Claims this project supports

- Hands-on query-first Cassandra data modeling, verified against a real
  3-node cluster
- Two real, documented operational incidents diagnosed and resolved
  during development
- Verified consistency-level/failure behavior (not just described)
- A load test with real observed latency numbers across three
  consistency levels, with the local-lab limitation (no real inter-node
  network latency) stated directly

## Claims this project does NOT support

- Prior professional Cassandra production experience
- Multi-datacenter replication or a real network-latency environment
- Repair/compaction scheduling in practice (discussed, not automated —
  see `docs/RUNBOOKS.md`'s repair section)
- Production-scale cluster sizing
