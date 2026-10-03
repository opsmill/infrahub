# Task Workers

> Part of: `dev/knowledge/backend/` | Related: [Async Tasks](async-tasks.md), [ADR-0003](../../adr/0003-asynchronous-tasks.md)

How a task worker finds, claims and starts flow runs, and what that means for the
[priority lanes](async-tasks.md#priority-lanes). The worker is `InfrahubWorkerAsync`
(`backend/infrahub/workers/infrahub_async.py`), a Prefect `BaseWorker` that runs every flow in its own
event loop; the enterprise worker subclasses it without changing how runs are claimed.

## From scheduled to running

A worker polls the work pool every `worker_polling_interval` seconds (default 2). Each poll asks the
Prefect server for runs due within the next 10 seconds (Prefect's prefetch window) across every queue
in the pool, and gets back up to 200 of them, ordered by queue precedence and then by scheduled time.
A poll changes nothing on the server: a run stays `SCHEDULED` until a worker claims it.

Claiming and starting one run takes seven sequential calls to the Prefect API, all through the
worker's own Prefect client, which holds 16 connections for the whole worker; the deployment and
flow reads are mostly answered from memory (see [Deployment and flow reads](#deployment-and-flow-reads)):

1. read the deployment, to check that it still exists;
2. propose `Pending` — this is the claim, and the server rejects it if another worker got there first;
3. read the deployment and the flow again, to build the job configuration;
4. add the worker labels to the run;
5. propose `Submitting`;
6. start the flow in the worker's event loop, which reports `Running` through a client of its own;
7. record the infrastructure id.

A run that has been claimed (`Pending` or later) belongs to one worker and is never reordered: queue
precedence orders runs only while they are still `SCHEDULED` on the server.

## Deployment and flow reads

Serve the deployment and flow reads of a claim from memory: the worker keeps each deployment and
flow it reads for 60 seconds (`InfrahubWorkerAsync._cache_definition_reads`,
`infrahub/workers/read_cache.py::ExpiringModelCache`). Prefect issues those three reads for every
claimed run, through the worker's client and with no way to hand them in, while Infrahub saves its
deployments only when the task manager is set up and never changes a flow; under a backlog the
reads made up about a sixth of all Prefect API requests. Each read returns a copy, concurrent reads
of a missing entry share one request, and a failed read is not kept.

The 60 seconds bound how long a worker goes on using a deployment after it changes on the server:

- a re-saved deployment reaches the claims of each worker within 60 seconds;
- deleting a deployment deletes its scheduled runs with it, so a worker still holding one of them
  from a poll fails to claim it and never starts it. A run the deletion leaves scheduled, such as
  one awaiting a retry, can still start within those 60 seconds instead of being cancelled; once
  the entry expires, the read fails and Prefect cancels the run.

## Bounded submission

Claim only as many runs as the submission window holds, from the head of the latest poll; leave the
rest scheduled on the server. A worker that claimed every run of every poll queued each later poll,
and every later high-priority run, behind the claims of the whole backlog on its 16 connections:
under a generator-driven backlog of computed attribute runs, branch creation waited about 40 times
longer than its own execution. Unclaimed runs keep their place in the server's priority order, so the
next poll brings a newly scheduled high-priority run to the head of the window.

The window holds eight runs, half of the client's connections, so a poll or a state proposal never
waits behind submissions. A slot is freed as soon as its flow has started, and the next candidate
of the latest poll is taken right away instead of waiting for the next poll. A new poll replaces the
candidates of the previous one. Under the same backlog, bounding the claim made branch creation about
ten times faster while the backlog drained at least as fast as with the unbounded claim.

The window bounds runs being claimed, not runs executing: a worker runs any number of flows at once.
Prefect's `--limit` caps executing flows instead, and a high-priority run then waits for a running
flow to finish, since nothing preempts a flow that has started.

## Reservations between workers

Every worker polls the same backlog, so two workers can take the same run from the head of their
polls. The server accepts the first `Pending` proposal and rejects the other, which costs the losing
worker one wasted claim; the window bounds how many such claims can be in flight at once. Without a
reservation, two workers working through the same poll lose a claim on most runs.

A worker can take a reservation before claiming instead, through the reservation it builds for its
window. The community worker builds one that always succeeds. The enterprise worker reserves each run
in the cache for 15 seconds, owned by its `WORKER_IDENTITY`, so concurrent workers claim different
runs: a worker may reserve a run it already holds, a taken run it does not submit gives its
reservation back, and a submitted run keeps its reservation until it expires, so a worker still
holding an older poll skips it.

The reservation must outlive a claim. With unbounded claiming a claim took longer than the 15-second
expiry under load, the reservation lapsed while the first worker was still claiming, and the second
worker claimed the same run.

## Known gaps

- A worker that dies between claiming a run and starting its flow leaves the run `Pending` for good.
  Zombie detection only watches the heartbeats of running flows (see
  [Liveness and zombie detection](async-tasks.md#liveness-and-zombie-detection)), and nothing returns
  a `Pending` run to the queue.
- A `create-branch` run is tagged with the branch it creates, so it shows in that branch's task list
  and in the unfiltered list, not in the list of the branch it was created from.

## See Also

- [Async Tasks](async-tasks.md) - workflows, priority lanes and their inheritance
- [ADR-0003: Asynchronous Tasks](../../adr/0003-asynchronous-tasks.md) - why Prefect
