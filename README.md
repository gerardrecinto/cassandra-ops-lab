# cassandra-ops-lab

A Cassandra data-modeling portfolio project built to close a genuine
hands-on gap. Query-first schema design, time-bucketed partitions,
TTL/tombstone-aware compaction, consistency-level tradeoffs, and real
failure/recovery testing — run against an actual local 3-node Cassandra
cluster (RF=3), not a single-node stand-in.

**Honesty note**: Cassandra was a genuine gap in my hands-on experience
before this project. Everything in this repo — including the two real
operational incidents documented below, which I hit and fixed while
building this, not fabricated for the README — was learned and verified
in this lab.

## Local quickstart

```bash
docker compose up -d cassandra-1
# wait for it to show UN in: docker exec cassandra-ops-lab-cassandra-1-1 nodetool status
docker compose up -d cassandra-2
# wait for UN again before starting the third -- see "Real incident" below for why
docker compose up -d cassandra-3

python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

python -m pytest tests/ -v
python scripts/failure_recovery_demo.py
python -m cassandra_ops_lab.loadtest.load_runner --n-events 300 --consistency LOCAL_QUORUM
```

**Observed**: 13/13 tests passing against the real 3-node cluster.

## Real incident #1: concurrent bootstrap token collision

Starting `cassandra-2` and `cassandra-3` at the same time in this lab
produced a real crash:

```
java.lang.RuntimeException: Bootstrap Token collision between
/172.22.0.3:7000 and /172.22.0.4:7000 (token 1128599039621199816
```

Two nodes joining a fresh cluster simultaneously can independently
generate the same random vnode token. Fix: stagger node startup — start
one, confirm `nodetool status` shows `UN` (not `UJ`), then start the
next. See `docs/RUNBOOKS.md` for the full writeup. This is why the
quickstart above starts nodes one at a time instead of `docker compose up -d`.

## Real incident #2: schema-propagation race right after DDL

Writing at `ALL` or `ONE` consistency immediately after creating a new
keyspace/table intermittently failed with:

```
cassandra.WriteFailure: ... INCOMPATIBLE_SCHEMA from /172.22.0.3:7000
```

DDL changes propagate via gossip and take a moment to reach every node;
writing before that finishes can hit a replica still on the old schema
version. Fix: a short sleep after `create_tables()` before issuing writes
(`scripts/failure_recovery_demo.py`, `loadtest/load_runner.py`) — a real
operational lesson about schema agreement timing, not a hypothetical one.

## Failure and recovery: observed

`scripts/failure_recovery_demo.py` stops one of three nodes mid-run and
shows the actual consistency-level behavior, not asserted from docs:

```
== all 3 nodes up ==
  baseline: WRITE SUCCEEDED at 5   (ALL)
  baseline: WRITE SUCCEEDED at 4   (QUORUM)

== stopping cassandra-ops-lab-cassandra-2-1 ==
== 1 of 3 nodes down ==
  degraded: WRITE FAILED at 5 -- Unavailable: Cannot achieve consistency level ALL
                                  (required_replicas=3, alive_replicas=2)
  degraded: WRITE SUCCEEDED at 4   (QUORUM -- needs 2 of 3, has 2)
  degraded: WRITE SUCCEEDED at 1   (ONE)

== restarting cassandra-ops-lab-cassandra-2-1 ==
== all 3 nodes back up ==
  recovered: WRITE SUCCEEDED at 5  (ALL)
```

`ALL` fails immediately (`Unavailable`, not a timeout — the coordinator
knew from gossip state it couldn't satisfy 3/3) while `QUORUM` and `ONE`
keep working with one node down, exactly matching RF=3 arithmetic.

## Load test: observed (this lab, local Docker, not production scale)

300 writes + 50 reads per run, single-threaded client, all three nodes on
one machine (no real network latency between them — see caveat below):

| Consistency | Write p50 | Write p95 | Write p99 | Read p50 | Read p95 |
|---|---|---|---|---|---|
| ONE | 7.3ms | 10.3ms | 17.1ms | 2.5ms | 4.5ms |
| LOCAL_QUORUM | 11.0ms | 14.3ms | 21.1ms | 4.1ms | 6.3ms |
| ALL | 10.0ms | 12.7ms | 14.7ms | 4.0ms | 5.0ms |

`ONE` is consistently fastest, as expected. `LOCAL_QUORUM` vs. `ALL` don't
show a clean, large separation here — all three nodes are on the same
Docker host with effectively no network latency between them, which mutes
the real-world cost of waiting for more replicas. In a real multi-AZ or
multi-region deployment, the `QUORUM` vs. `ALL` gap would be dominated by
actual network round-trip time, not shown accurately by this single-host
lab. Stated as a limitation, not glossed over — re-run
`scripts/failure_recovery_demo.py`'s cousin `loadtest/load_runner.py`
yourself with `--consistency` to reproduce.

## Query-first schema

See `cassandra_ops_lab/schema/ddl.py`'s module docstring for the full
reasoning and `docs/ARCHITECTURE.md` for the request-flow diagram. Four
queries decided first, three tables (one denormalized per access
pattern), no joins — the Cassandra way.

## Repo layout

```
cassandra_ops_lab/
  connection.py               cluster/session setup
  events.py                    synthetic event generator
  schema/ddl.py                 query-first table DDL, TTL/TWCS/counter reasoning
  repository/deploy_history.py  one function per query pattern, LOGGED batch for denormalized writes
  loadtest/load_runner.py       write/read latency by consistency level
docker-compose.yml              3-node Cassandra cluster (RF=3), heap-capped for a local laptop
scripts/
  failure_recovery_demo.py      real node-stop/restart test against consistency levels
tests/                            13 tests, real integration against the live 3-node cluster
docs/                              architecture, runbooks (2 real incidents), Cassandra-vs-Postgres,
                                   security, cost, troubleshooting, portfolio summary
```
