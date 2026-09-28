# Cost notes

Everything here runs in local Docker containers — no managed Cassandra
service (Astra DB, Keyspaces, or self-managed EC2/EKS nodes) was
provisioned, so no cloud cost was incurred.

## Design decisions that would matter for cost at production scale

- **TTL + TimeWindowCompactionStrategy** (`schema/ddl.py`) bounds storage
  growth automatically — expired data's SSTables get dropped wholesale
  rather than needing a manual archival/deletion job, which matters
  directly for storage cost on a workload with a natural retention window.
- **`REPLICATION_FACTOR` is set per-keyspace, not hardcoded globally** —
  this lab uses RF=3 to actually exercise quorum/failure behavior; a
  lower-value, less-critical keyspace in the same cluster could run RF=2
  if the durability tradeoff were acceptable, without changing anything
  about the cluster itself.
- **`MAX_HEAP_SIZE=500M` per node** (`docker-compose.yml`) is a
  local-lab-only setting to fit 3 JVM nodes in a resource-constrained
  Docker Desktop VM (a real first attempt at 3 nodes with default heap
  sizing OOM-killed all three — see `docs/TROUBLESHOOTING.md`). Production
  heap sizing is a real, separate cost/performance tuning exercise based
  on actual node memory and workload, not something this lab's numbers
  should inform directly.

## What's not modeled

No production cluster sizing, no comparison against a managed service's
per-node or per-request pricing. This project demonstrates the modeling
and operational patterns; sizing a real cluster's node count, instance
type, and replication topology depends on actual production read/write
volume this lab doesn't have.
