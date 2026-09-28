# When Postgres would be the better choice

This project uses Cassandra for a reason specific to its access pattern —
not because Cassandra is generally "better" at storing data. This
document exists to be honest about that boundary, since claiming
Cassandra is a default choice would misrepresent the tool.

## Where Cassandra fits (and this project's access pattern)

- Every query is known in advance and keyed by a specific partition key
  (`service` [+`environment`] +`day`) — see `schema/ddl.py`.
- Write volume that needs to scale horizontally across many nodes by
  adding capacity, not by scaling one machine up.
- Time-series data with a natural expiration (`default_time_to_live`) and
  no need for cross-entity joins.
- Tunable consistency per operation (this project uses `LOCAL_QUORUM`
  writes / `LOCAL_ONE` reads — see `docs/ARCHITECTURE.md`), trading some
  consistency for availability and latency where the data's actual
  durability needs allow it.

## Where Postgres would be the better choice

- **Ad-hoc queries on columns that aren't part of a partition key.**
  "Show me all deploys where duration_seconds > 300 regardless of
  service" is a `WHERE` clause away in Postgres. In Cassandra it requires
  either a secondary index (real performance cliff at scale) or
  `ALLOW FILTERING` (a full partition scan, actively discouraged) — this
  project's tables intentionally cannot answer that query efficiently,
  because it wasn't one of the four queries decided ahead of time.
- **Joins across entities.** If deploy events needed to be joined against
  a `services` table (owner, on-call rotation, tier) in the same query,
  that's a Postgres join, not something Cassandra does at all — Cassandra
  would require denormalizing the service metadata into every event row
  (more write amplification, staler data) or a second round-trip from the
  application.
- **Multi-row ACID transactions.** This project's own counter-update gap
  (`docs/ARCHITECTURE.md`'s "Why the counter update isn't in the batch")
  is a direct example: Postgres would make that a single transaction with
  a real all-or-nothing guarantee across both tables and the count, no
  named tradeoff needed.
- **Lower operational complexity for moderate scale.** A single Postgres
  instance (with read replicas as needed) is simpler to operate, back up,
  and reason about than a multi-node Cassandra ring, gossip protocol, and
  repair/compaction schedule — worth it only once the workload's actual
  scale or availability requirements justify that complexity. The sibling
  `kafka-ops-lab` project uses Postgres specifically for this reason: it
  needs `ON CONFLICT DO NOTHING` transactional idempotency, which is a
  much more natural fit for Postgres than Cassandra's lightweight
  transactions (Paxos-based, higher latency, meant for rare use, not a
  per-row idempotency pattern).

## The honest summary

Cassandra was the right choice **for this project's specific,
decided-in-advance query set**, scoped to that. The `kafka-ops-lab`
project in this same portfolio deliberately uses Postgres for its
idempotent sink, for exactly the reasons above — each tool matched to
the access pattern it actually fits.
