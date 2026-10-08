# 21. Resource-allocation telemetry: container limits, carried by the heartbeat, in new blocks

**Status:** Accepted
**Date:** 2026-10-08
**Author:** @opsmill-team

**Source:** `specs/archive/infp-631-resource-telemetry/research.md` (D2–D7, D11–D17)

## Context

Infrahub tiers are priced on the compute a deployment gives Infrahub, and most deployments are
air-gapped, so the anonymous daily telemetry snapshot has to tell a reviewer how much CPU and memory
the database, the API server and the task workers are allowed to use. Before this decision the
snapshot reported the database's figures only. Three questions had to be settled:

- What "available" and "assigned" mean for a process that runs in a container.
- How figures that only each process can read reach the one task worker that builds the report.
- How to add them to a payload that a separate receiving service already ingests.

## Decision

**Measure the allocation that is enforced, not the machine.** Each API server and task-worker
process reads its own limits from two sources: the Linux cgroup files, where Docker or Kubernetes
writes the limit it puts on a container, and `psutil` for the whole machine.

- If a limit is set, the limit is reported. If none is set, the machine's figures are reported. The
  files are read at every level the process can see, the tightest limit winning, cgroup v2 first
  and v1 as a fallback.
- A limit file that exists but cannot be read makes the figure unknown (`null`), never the
  machine's figure, which could be far too high.
- `processor_available` is the smallest of the machine's CPU count, the container's CPU limit
  rounded down (at least 1) and the number of CPUs the process is pinned to. `processor_assigned`
  is the container's CPU limit rounded up, and `null` when none is set; it is never filled in from
  the machine. All CPU counts are logical CPUs.
- `memory_total` is the tightest memory limit, or the machine's memory without one.
  `memory_available` is the smallest free amount under any limit, never below zero.
- The limits are read again every 10 seconds, so a live change to a limit shows up without a
  restart. Where the limit files are, and the machine's CPU count, are read once.
- For the database, `processor_assigned` is Neo4j's `server.cypher.parallel.worker_limit` setting;
  its default, 0, is reported as `null`. The other database figures are the ones Neo4j already
  reported.

**Carry the reading through the liveness heartbeat.** Every 10 seconds the main loop starts a read
of the figures on a separate thread, so that a slow read cannot hold up requests and flows, and hands
the reading to the heartbeat thread through a locked slot in memory. Every 5 seconds the
heartbeat writes the latest reading to the cache next to its "alive" key, with the same 15-second
expiry. Once a day the report reads every reading back from the cache. Each reading carries the
container's name, which is never sent, so readings from the same container can be grouped. The name
is the hostname followed by the container's process ID namespace, because separate containers can
share a hostname, for example when they use the host's network.

**Add new blocks and leave existing fields alone.** `workers` keeps its meaning: it counts every
worker process. Two new blocks, `server` and `task_workers`, count their own component's processes
the same way and carry `per_worker`: one worker's share of its container. The share is the most
complete reading of the component divided by the number of processes that reported from its
container, with CPU figures kept to two decimals and memory in whole bytes, so `per_worker × active`
is the component's total. The database block gains `processor_assigned`. `payload_format` stays the
same until the receiving service confirms it accepts the new fields.

## Consequences

### Positive

- One snapshot shows how much compute a deployment gives Infrahub, without contacting the customer.
  The snapshot is stored locally even when the deployment does not send telemetry.
- A figure never overstates the allocation: an unreadable limit is unknown, and an assigned figure
  is never invented.
- A live limit change reaches the cache within about 15 seconds.
- A worker busy with a long task keeps reporting for as long as it is alive, and a stopped worker's
  reading disappears within 15 seconds, so the counts and the figures describe the same processes.
- No existing field changes, so current ingestion keeps working.

### Negative

- A limit set only on a Kubernetes pod, when the container itself has none, cannot be seen from
  inside the container. Neither can Kubernetes CPU requests, which reserve CPU but do not limit it.
- The share assumes every copy of a component runs with the same settings. It reads high for a
  moment after a process starts, until that process has stored its first reading.
- `processor_assigned` is `null` both when no limit is set and when it cannot be read. The pair of
  CPU figures tells the two apart: no limit leaves `processor_available` set.
- `psutil` becomes a runtime dependency.
- The reading in the cache can be up to about 15 seconds old, or older while the main loop is busy
  with a long task. Limits rarely change, so this is acceptable.

### Neutral

- `server.total + task_workers.total` equals `workers.total`, except for a process that stopped
  about two hours earlier and is only remembered by its 2-hour presence key.
- Neo4j rounds a fractional CPU limit up for its usable figure, while the other components round it
  down, so under a fractional limit the two can differ by one.
- Older parts of the report, such as building the database block and reading the worker list, still
  stop the whole report when they fail. This decision does not change that.

## Alternatives Considered

### Report the machine's figures

Inside a container `psutil` still sees the whole machine. On an 18-CPU machine with a container
limited to 2 CPUs it reports 18.

### Read and store the figures on a main-loop schedule

A long task that keeps the main loop busy would let the reading expire while the heartbeat kept the
worker alive, so the worker would be counted with no figures.

### Read the figures on the heartbeat thread

The thread only writes to the cache, so that nothing can stall the signal that a worker is alive.
Reading files there could block it.

### A separate flow to collect the figures

It would duplicate the heartbeat's job of knowing which workers are alive, with more moving parts.

### Sum the figures over all containers

Summing needed each container counted once, two different rules for empty values, and an undercount
whenever a container stayed silent, which a consumer could not detect from one snapshot.

### Report each worker's full container figures

`per_worker × active` would overstate the API server by its number of processes per container: a
4-CPU container shared by 4 processes would read as 16 CPUs.

### Narrow `workers.total` to task workers, or put the task-worker figures in `workers`

`workers.total` is used downstream, so narrowing it would change an existing series even with its key
and type unchanged. Putting the task-worker figures next to a count that includes API server
processes would make `per_worker × active` wrong.

### Raise `payload_format` with the change

A receiver that checks the version string could break. The change is additive, so the version is
raised once the receiving service confirms it accepts the new fields.
