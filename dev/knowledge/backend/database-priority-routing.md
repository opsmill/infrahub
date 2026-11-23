# Database Routing by Request Priority

> Part of: `dev/knowledge/backend/` | Related: [query-pattern.md](query-pattern.md), [api-backpressure.md](api-backpressure.md), [async-tasks.md](async-tasks.md)

How the read sessions of a Neo4j cluster deployment run on the writer (the leader) or on a reader,
depending on the priority (high, medium, low) of the API request or workflow run that opens them.
The setting is `INFRAHUB_DB_WRITER_READ_PRIORITIES`; the operator steps are in the
[high availability guide](../../../docs/docs/deploy-manage/install-configure/production-deployment/high-availability.mdx#run-the-reads-of-a-priority-on-the-cluster-leader).

## One driver, two destinations

Keep a single driver. A Neo4j driver fixes its routing policy (`INFRAHUB_DB_POLICY`) when it is
created and caches one routing table per database, so a session can choose only its access mode:
`READ_ACCESS` runs it on a reader the policy allows, `WRITE_ACCESS` on the writer. A read session
that serves a priority in `writer_read_priorities` opens with `WRITE_ACCESS`; every other read
session opens with `READ_ACCESS`. Sending different priorities to different readers would need a
driver, and a connection pool, per policy.

A read session that opens with `WRITE_ACCESS` needs the writer: while the cluster has no leader,
for example during a leader election, it cannot run, where a `READ_ACCESS` session keeps running on
a follower.

The setting requires the `neo4j` protocol and database type, because only a routing driver sends a
read session elsewhere than the writer.

## Only read sessions follow the priority

Open a session with `start_session(read_only=True)` when its work can run on a reader. A write
session (the default) runs on the writer whatever its priority, because only the writer accepts
writes.

- GraphQL query resolvers each open a read session, so the reads of the GraphQL API follow the
  priority of the request, including the queries a workflow sends through the SDK (see below).
- The session the GraphQL app opens for the request, and the one REST endpoints get from `get_db`,
  are write sessions: authentication, branch lookup and mutations run on the writer.
- Infrahub passes no bookmarks between sessions. A read session on a follower can miss a write that
  another session committed just before, so keep a read that must see that write in the write
  session, or in a transaction of it.

## Keep reads moved to the writer out of the stress signal

A reference query that runs in a read session moved to the writer does not feed the admission
layer's [database-stress signal](api-backpressure.md#the-database-stress-signal). Each worker keeps
one floor and one window, and the writer and the readers carry different loads, so mixing their
timings would compare a reader's timing with the writer's best one.

- GraphQL loads permissions, and with them the reference query, in a read-only session, so the
  query follows the request priority: requests of a priority in `writer_read_priorities` add no
  sample.
- REST endpoints load permissions in their write session, which runs on the writer for every
  priority; those samples still feed the signal.

## Where the priority comes from

`infrahub/execution_priority.py` holds the execution priority in a context variable that a session
reads when it opens. Tasks started inside a binding inherit it.

- API: `RequestPriorityMiddleware` binds the class of the `X-Priority` header for each HTTP request.
  A missing or unknown value binds `medium`, as in the admission layer. WebSockets bind none.
- Task workers: the worker binds the priority of the work queue the flow run came from, which is
  the lane it runs in also when only the catalogue default chose it.
- Startup, the scheduler and the CLI bind none, and their read sessions open with `READ_ACCESS`.

Build an SDK client with `get_client()` inside the request or flow run that uses it.
`build_client()` sets the client's default priority from the bound priority, so every query the
client sends carries it as `X-Priority`. Outside of a binding, the client keeps the default that
`INFRAHUB_PRIORITY` sets, or sends no priority and the API serves its queries as `medium`.

A flow that sets the client's request context from its `InfrahubContext` sends the priority of that
context instead. That is usually the lane of the run, but not for a run that an automation started:
the automation dispatches it to its deployment's default queue, while its context carries the
priority of the work that emitted the event. Such a run sends its SDK queries at one priority and
opens its own database sessions at another.
