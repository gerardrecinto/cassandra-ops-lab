# Runbooks

## Incident: two nodes bootstrapping simultaneously (real, hit in this lab)

**What happened, verified in this repo's own build**: starting
`cassandra-2` and `cassandra-3` at the same time
(`docker compose up -d cassandra-2 cassandra-3`) caused node3 to crash on
startup with:

```
java.lang.RuntimeException: Bootstrap Token collision between
/172.22.0.3:7000 and /172.22.0.4:7000 (token 1128599039621199816
```

Two nodes joining a fresh cluster at the same moment can independently
generate the same random token (`num_tokens` vnode allocation), and
Cassandra refuses to let both claim it. The fix that worked here:
restart the failed node by itself, after the other node already holds
its tokens (`docker compose up -d cassandra-3` alone, once `cassandra-2`
was confirmed `UN` in `nodetool status`) — the second attempt picked
different tokens and joined cleanly.

**Runbook**: when bootstrapping multiple new nodes into a cluster,
stagger them — start one, confirm `nodetool status` shows it `UN`
(Up/Normal, not `UJ` Up/Joining), then start the next. This is a real
operational constraint, not a rare edge case; it reproduced on the first
attempt in this lab.

## Consumer-facing symptom: reads/writes failing after a node goes down

1. Check `nodetool status` (from any live node): a `DN` (Down/Normal)
   entry identifies which node is unreachable, vs. gossip just being slow
   to notice (check again after ~10s — this repo's
   `scripts/failure_recovery_demo.py` waits 10s after `docker stop`
   before asserting anything, for this reason).
2. Check what consistency level the failing query used. With RF=3:
   - `ONE` / `LOCAL_ONE`: tolerates 2 nodes down. A single node failure
     should never break this.
   - `QUORUM` / `LOCAL_QUORUM`: tolerates 1 node down (needs 2 of 3).
     Two nodes down breaks it.
   - `ALL`: tolerates zero nodes down. Any single failure breaks it
     immediately — verified directly in `scripts/failure_recovery_demo.py`,
     which stops one of three nodes and shows `ALL` writes failing with
     `Unavailable` while `QUORUM` and `ONE` continue to succeed.
3. If the failure is `Unavailable` (not a timeout), the coordinator knew
   upfront it didn't have enough live replicas — this is gossip state,
   not the query actually being attempted and failing partway. If it's a
   `WriteTimeout`/`ReadTimeout` instead, the query WAS attempted and some
   replicas didn't respond in time — check for network partition or an
   overloaded (not fully down) node, a different failure mode than a
   clean node stop.

## Suspected uneven partition or slow queries

Check the actual partition key values in use — if a service has been
running far longer than others or deploys far more frequently, its daily
partitions will be larger, but bounded by design (one day's worth of
deploys, not that service's entire history) precisely because of the
`day` bucketing in every partition key (`schema/ddl.py`). If a specific
service's queries are consistently slow relative to others, check
`nodetool tablestats <keyspace>.<table>` for that partition's actual row
count and compare to the table's typical partition size — a partition an
order of magnitude larger than its siblings usually means an
unusually deploy-heavy service, not a schema problem.

## Repair

Not run in this lab (single test session, no time for data to drift
between replicas from missed writes/hints). For a real deployment:
`nodetool repair` should run on a schedule (commonly weekly, must be more
frequent than `gc_grace_seconds`, default 10 days, to avoid resurrecting
deleted data from a replica that missed the delete) — not included here
as an automated job, stated as a gap rather than implied to exist.
