# Database Routing by Request Priority

> Part of: `dev/knowledge/backend/` | Related: [query-pattern.md](query-pattern.md), [api-backpressure.md](api-backpressure.md), [async-tasks.md](async-tasks.md)

How the read sessions of a Neo4j cluster deployment run on the cluster servers chosen for the
priority (high, medium, low) of the API request or workflow run that opens them. The settings are
`INFRAHUB_DB_POLICY_{HIGH,MEDIUM,LOW}` and `INFRAHUB_DB_WRITER_READ_PRIORITIES`; the operator steps
are in the [high availability guide](../../../docs/docs/deploy-manage/install-configure/production-deployment/high-availability.mdx#route-read-queries-by-request-priority).

## Only read sessions are routed

Open a session with `start_session(read_only=True)` when its work can run on another server than
the writer. A Neo4j routing policy filters only the readers of the routing table, and the writer
accepts every write, so a write session (the default) runs on the writer whatever its priority.

- GraphQL query resolvers each open a read session, so the reads of the GraphQL API are routed,
  including the queries that workflows send through the SDK with their `X-Priority`.
- The session the GraphQL app opens for the request, and the one REST endpoints get from `get_db`,
  are write sessions: authentication, branch lookup and mutations run on the writer.
- Infrahub passes no bookmarks between sessions. A read session on a follower can miss a write that
  another session committed just before, so keep a read that must see that write in the write
  session, or in a transaction of it.

## Where the priority comes from

`infrahub/database/routing.py` holds the execution priority in a context variable that a session
reads when it opens. Tasks started inside a binding inherit it.

- API: `RequestPriorityMiddleware` binds the class of the `X-Priority` header for each HTTP request.
  A missing or unknown value binds `medium`, as in the admission layer. WebSockets bind none.
- Task workers: the worker binds the priority of the work queue the flow run came from, which is
  the lane it runs in also when only the catalogue default chose it.
- Startup, the scheduler and the CLI bind none, and their read sessions use the default driver.

## One driver per policy

The routing policy of a Neo4j driver is part of its URI (`?policy=<name>`) and fixed at creation,
so each distinct policy has its own driver and connection pool of up to `max_connection_pool_size`
connections per server. Priorities that share a policy share a driver, and a priority whose policy
equals `INFRAHUB_DB_POLICY` reuses the default driver.

A priority in `writer_read_priorities` opens its read sessions on the default driver with
`WRITE_ACCESS`, which sends them to the writer. The settings reject a priority with both a policy
and a writer read, and require the `neo4j` protocol and database type.

`build_database` opens a read connection through every policy driver at startup, so a policy the
cluster does not define stops startup instead of failing every read of that priority.
