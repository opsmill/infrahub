# 21. Resource-allocation telemetry: container limits, stored by each process, in new blocks

**Status:** Accepted
**Date:** 2026-10-08
**Author:** @opsmill-team

**Source:** `specs/infp-631-resource-telemetry/research.md` (D2–D7, D11–D20)

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
- The limits are read again every 5 minutes, so a live change to a limit shows up without a
  restart. Where the limit files are, and the machine's CPU count, are read once.
- For the database, `processor_assigned` is Neo4j's `server.cypher.parallel.worker_limit` setting;
  its default, 0, is reported as `null`. The other database figures are the ones Neo4j already
  reported. Its `memory_total` is the container's memory limit, or the whole machine without one,
  so a database sized only through its own settings, as the enterprise chart presets do, needs one
  more figure.
- For the database, `memory_assigned` is Neo4j's heap (`server.memory.heap.max_size`) plus its page
  cache (`server.memory.pagecache.size`), and `null` unless both are set: without them Neo4j works
  out its sizes from the memory it can see, which `memory_total` already reports.

**Store each reading from the read that takes it, and use only live workers' readings.** At startup
and every 5 minutes the main loop starts a read of the figures on a separate thread, so that a slow
read cannot hold up requests and flows, and stores the reading in the cache with a 2-hour expiry, so
a long task that keeps the main loop from reading again does not lose it. The heartbeat thread
only writes the "alive" keys. Once a day the report reads the readings back from the cache and
keeps those of the workers whose "alive" key is still set, taken from the same list of workers it
counts, so a stopped worker's reading is ignored although it stays in the cache. A read that fails
on every try stores nothing, so the last stored reading is kept.

**Add new blocks and leave existing fields alone.** `workers` keeps its meaning: it counts every
worker process. Two new blocks, `server` and `task_workers`, count their own component's processes
the same way and carry two more fields:

- `per_container`: the CPU and memory of one of the component's containers, whole, from its most
  complete reading.
- `processes_per_container`: how many processes share that container. Each reading carries it. For
  an API server process it is gunicorn's worker count (`-w`), which the gunicorn worker class puts
  in the process's environment before the app loads. A process that gunicorn did not start, such as
  a task worker, counts 1.

The component's total is `per_container × active ÷ processes_per_container`, and every figure is a
whole number. The database block gains `processor_assigned` and `memory_assigned`.
`payload_format` stays the same until the receiving service confirms it accepts the new fields.

## Consequences

### Positive

- One snapshot shows how much compute a deployment gives Infrahub, without contacting the customer.
  The snapshot is stored locally even when the deployment does not send telemetry.
- A figure never overstates the allocation: an unreadable limit is unknown, and an assigned figure
  is never invented.
- The report shows how big each component's containers are and how many processes share one, so a
  container running more processes than it has CPUs is visible directly.
- A live limit change reaches the cache within about 5 minutes, or later while the main loop is busy
  with a long task, still well before the next daily report.
- A worker busy with a long task keeps its reading for up to 2 hours, and the report stops using a
  stopped worker's reading once its "alive" key expires, within 15 seconds, so the counts and the
  figures describe the same processes.
- The heartbeat writes only the "alive" keys, so a failed or slow telemetry write cannot stop it from
  refreshing the primary API server election or the presence key.
- No existing field changes, so current ingestion keeps working.

### Negative

- A limit set above the container's own view, for example on a Kubernetes node that itself runs in a
  container, cannot be seen from inside the container. Neither can Kubernetes CPU requests, which
  reserve CPU but do not limit it. A limit set only on a pod is seen: on Kubernetes 1.37 the pod's
  limit is also written on a container that sets none. Older versions were not checked.
- One container stands for every copy of a component, so every copy is assumed to run with the same
  settings.
- The process count comes from how gunicorn was started, not from the processes that run. An API
  server started another way with several processes, for example by `uvicorn --workers`, counts as
  one process per container, so its total is overstated. Every way OpsMill ships Infrahub (Docker
  Compose, both Helm charts) starts the API server through gunicorn with this worker class.
- While a container runs fewer processes than its count, for example for the moment gunicorn takes
  to restart one, `active` is lower and the total reads low until the process is back.
- For the API server and task workers, `processor_assigned` is `null` both when no limit is set
  and when it cannot be read. The pair of CPU figures tells the two apart: no limit leaves
  `processor_available` set.
- For the database, `processor_assigned` is `null` both when `server.cypher.parallel.worker_limit`
  is left at its default and when it cannot be read, and `processor_available`, which comes from
  Neo4j itself, is set either way. Only the warning that a failed read writes to the log tells the
  two apart.
- The database's `memory_assigned` is `null` both when a setting is unset and when the read fails;
  only the logged warning tells them apart. Neo4j returns the settings rounded to two decimals of
  their unit, so each setting can be off its configured size by up to 0.005 of that unit: about
  5 MiB at GiB scale, about 5 GiB at TiB scale. The Neo4j Docker image
  sets a 512 MiB page cache on its own when none is configured, so under Docker only the heap
  setting decides whether the figure is reported.
- `psutil` becomes a runtime dependency.
- The reading in the cache can be up to about 5 minutes old, or older while the main loop is busy
  with a long task. Limits rarely change, so this is acceptable for a daily report. Free memory does
  change on its own, so it describes a moment up to 5 minutes before the report. A process whose
  first read fails has no reading until a later read succeeds.
- A worker whose main loop is held up for more than 2 hours loses its reading. After the cache is
  emptied, for example by a restart, the readings come back at each process's next read, within
  5 minutes.

### Neutral

- `server.total + task_workers.total` equals `workers.total`, except for a process that stopped
  about two hours earlier and is only remembered by its 2-hour presence key, normally for at most
  about 5 minutes.
- Neo4j rounds a fractional CPU limit up for its usable figure, while the other components round it
  down, so under a fractional limit the two can differ by one.
- Older parts of the report, such as building the database block and reading the worker list, still
  stop the whole report when they fail. This decision does not change that.

## Alternatives Considered

### Report the machine's figures

Inside a container `psutil` still sees the whole machine. On an 18-CPU machine with a container
limited to 2 CPUs it reports 18.

### Store the reading with the "alive" key's 15-second expiry

A long task that keeps the main loop busy would let the reading expire while the heartbeat kept the
worker alive, so the worker would be counted with no figures.

### Carry the reading through the liveness heartbeat

The main loop handed each reading to the heartbeat thread through a locked slot in memory, and every
5-second beat wrote it next to the "alive" key with the same 15-second expiry. The beat wrote the
same reading about 60 times between two reads, and the slot was a process-wide object of the kind the
component design rules do not allow. The telemetry write also ran inside the beat's time limit,
before the primary API server election and the presence key: when it failed or ran out of time, the
beat skipped those two as well.

### Read the figures every 10 seconds

The report runs once a day, so the extra reads bought nothing, and a limit file that exists but
cannot be used logs a warning on every read: 8,640 identical warnings a day per process.

### Read the figures on the heartbeat thread

The thread only writes to the cache, so that nothing can stall the signal that a worker is alive.
Reading files there could block it.

### A separate flow to collect the figures

It would duplicate the heartbeat's job of knowing which workers are alive, with more moving parts.

### Sum the figures over all containers

Summing needed each container counted once, two different rules for empty values, and an undercount
whenever a container stayed silent, which a consumer could not detect from one snapshot.

### Divide each container's figures among its processes

The report sent one process's share: the container's figures divided by the number of processes that
had stored a reading from it, so `per_worker × active` was the total. A reader could not see how big
a container was or how many processes shared it: a 2-CPU container running 2 processes and an 8-CPU
container running 8 sent the same report. Grouping the readings by container needed a container name
built from the hostname and the process ID namespace, because separate containers can share a
hostname, and a rule that a failed read still counted as a process sharing its container. The CPU
shares were decimals, and a whole-number share had to be sent as an integer for the telemetry
endpoint's checksum check. The share also read high until every process of a container had stored
its first reading.

### Report each container whole without the process count

`per_container × active` would overstate the API server by its number of processes per container: a
4-CPU container shared by 4 processes would read as 16 CPUs.

### Narrow `workers.total` to task workers, or put the task-worker figures in `workers`

`workers.total` is used downstream, so narrowing it would change an existing series even with its key
and type unchanged. Putting the task-worker figures next to a count that includes API server
processes would make the component's total wrong.

### Raise `payload_format` with the change

A receiver that checks the version string could break. The change is additive, so the version is
raised once the receiving service confirms it accepts the new fields.
