# Security notes

## What's implemented

- Schema validation is enforced at the CQL level (typed columns) —
  malformed inserts fail at the driver/server boundary, not silently.

## Known limitations (stated, not hidden)

- **No authentication.** `docker-compose.yml` runs Cassandra with the
  default `AllowAllAuthenticator`/`AllowAllAuthorizer` — anyone with
  network access to port 9042 has full read/write access. A production
  deployment needs `PasswordAuthenticator` at minimum, ideally backed by
  a real identity provider, plus role-based `CassandraAuthorizer` grants
  scoped per keyspace.
- **No encryption in transit or at rest.** `client_encryption_options`
  and `server_encryption_options` are both left at defaults (disabled) in
  this lab. Production needs TLS for client-to-node and node-to-node
  traffic at minimum.
- **No network isolation.** All three nodes and the client run on one
  Docker host's bridge network; a real deployment needs the nodes
  isolated to a private network/VPC with only the application tier able
  to reach port 9042.
