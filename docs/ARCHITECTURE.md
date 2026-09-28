# Architecture

## Query-first schema design

See `cassandra_ops_lab/schema/ddl.py`'s module docstring for the full
reasoning. Summary: four queries were written down first, then one table
per query pattern was designed to answer it directly — no joins, no
normalization, denormalized copies kept in sync via a LOGGED batch.

```
producer (events.py, or a real upstream service)
      |
      v
insert_deploy_event() -- repository/deploy_history.py
      |
      +-- LOGGED BatchStatement (atomic, all-or-nothing):
      |     - deploy_events_by_service_day        (PK: service, day)
      |     - deploy_events_by_service_env_day     (PK: service, environment, day)
      |
      +-- separate UPDATE (NOT atomic with the batch above):
            - deploy_counts_by_service_day counter (PK: service, day)
```

## Why the counter update isn't in the batch

Cassandra does not allow a counter mutation and a non-counter mutation in
the same `BatchStatement`. This is a hard driver-level constraint, not a
design choice (verified in
`tests/test_ddl_constraints.py::test_counter_table_cannot_mix_non_counter_columns`
and, at the batch level, by construction in `insert_deploy_event`). The
real consequence: if the process dies after the LOGGED batch commits but
before the counter UPDATE executes, `deploy_counts_by_service_day` under-counts
relative to the actual number of rows in `deploy_events_by_service_day`.
For a dashboard aggregate, that's an acceptable, named tradeoff — this
isn't a table anyone reconciles a financial ledger against.

## Consistency-level choice for this workload

Time-series operational metadata (deploy events), not financial data —
losing visibility into one write for a few seconds during a node failure
is a materially different risk than losing a financial transaction.
`LOCAL_QUORUM` writes / `LOCAL_ONE` reads (this repo's defaults in
`repository/deploy_history.py`) tolerate one node down out of RF=3 without
blocking, which matches this data's actual durability requirement. `ALL`
would block on any single node failure — verified directly in
`scripts/failure_recovery_demo.py`'s "degraded" section, not asserted
from documentation. See `docs/RUNBOOKS.md` for what each consistency
level costs and tolerates.

## Time bucketing and TWCS compaction

Covered in `schema/ddl.py`'s docstring in depth — short version: `day` in
every partition key bounds partition size, `default_time_to_live` expires
data after 90 days, and `TimeWindowCompactionStrategy` lets Cassandra drop
entire expired time-window SSTables without reading through them, which
`SizeTieredCompactionStrategy` (the default) doesn't do as cleanly for
this write pattern.

## When Postgres would be the better choice

See `docs/CASSANDRA_VS_POSTGRES.md` for the full comparison. Short
version: this project chose Cassandra because the access pattern is
"append-only time-series, always queried by a known partition key,
horizontally scalable write volume" — exactly what Cassandra is built
for. The moment a query needs an ad-hoc `WHERE` on a non-key column, a
join across entities, or a transactional multi-row update with real ACID
guarantees, Postgres is the better tool, and forcing that access pattern
into Cassandra (secondary indexes, `ALLOW FILTERING`) is a common
anti-pattern this project deliberately avoids.
