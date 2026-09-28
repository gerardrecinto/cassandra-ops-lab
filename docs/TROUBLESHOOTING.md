# Troubleshooting

## All 3 nodes get OOM-killed (exit code 137) on `docker compose up -d`

Hit this in the first attempt building this repo: starting all 3 nodes
simultaneously with Cassandra's default (auto-calculated) heap sizing
exhausted Docker Desktop's memory allocation (7.65GB total on the machine
this was built on) — each JVM tries to claim roughly 1/4 of the host's
visible memory, and 3 nodes doing that simultaneously overcommits badly.
Fix: `MAX_HEAP_SIZE`/`HEAP_NEWSIZE` env vars in `docker-compose.yml`,
capped to 500M/100M per node, plus a `mem_limit: 1400m` per container.
Check `docker info | grep -i memory` for your actual Docker Desktop
allocation before assuming 3 nodes will fit.

## `Bootstrap Token collision` on node startup

See README's "Real incident #1" and `docs/RUNBOOKS.md` — don't start
multiple fresh nodes simultaneously; stagger them and confirm `UN` status
between each.

## `INCOMPATIBLE_SCHEMA` errors on writes right after creating tables

See README's "Real incident #2" — add a short sleep after DDL execution
before writing, to let schema propagate via gossip to all nodes.

## Tests skip with "local Cassandra cluster not reachable"

Bring up all 3 nodes per the README's staggered-startup quickstart, and
confirm `docker exec cassandra-ops-lab-cassandra-1-1 nodetool status`
shows all three as `UN` before running tests — `pytest`'s fixture
(`tests/conftest.py`) only checks the driver can connect at all, not that
the full cluster is healthy, so tests can still intermittently fail (not
skip) if a node is still joining.

## `cqlsh` / driver connects but keyspace creation seems to hang or error transiently right after node3 joins

Observed in this lab: querying immediately after a node finishes joining
can hit brief timeouts while it finishes catching up internally. Retrying
after a few seconds resolved it every time this was hit — not a
persistent failure.
