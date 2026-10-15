# Contract: CPU and memory figures in the telemetry payload

**Read by**: the team that runs the telemetry receiving service and data mart.
**Produced by**: Infrahub's daily telemetry report (`send_telemetry_push`).
**Kind of change**: additions only. The database block gains one figure, and two new blocks, `server` and `task_workers`, describe the API server and the task workers. No existing field is renamed, removed, retyped or changes meaning; `workers` is exactly as before.
**Version**: `payload_format` stays `20260628` for now. It will be raised once the receiving service confirms it accepts the new fields (research D13). A consumer that expects the old shape keeps working.

## What is added

Only the additions are shown; everything else is unchanged.

```jsonc
// Illustrative deployment: Neo4j on a 32-core node with the `large` enterprise preset's
// 16-worker parallel runtime limit, one API server container running 4 gunicorn processes
// (the compose default, WEB_CONCURRENCY=4) limited to 4 CPUs / 4 GiB with 2.5 GiB free,
// and two task-worker containers limited to 4 CPUs / 4 GiB each with 3 GiB free.
{
  "payload_format": "20260628",              // unchanged for now
  "data": {
    "database": {
      // ... existing database fields ...
      "system_info": {                       // null when the database is not Neo4j
        "processor_available": 32,           // existing: CPUs Neo4j can use
        "processor_assigned": 16,            // NEW: CPUs its parallel query engine is set to use; null when not set
        "memory_total": 67435982848,         // existing: bytes
        "memory_available": 47034888192,     // existing: free bytes
        "memory_assigned": 50465865728       // NEW: heap + page cache Neo4j is set to use (31 GiB + 16 GiB); null unless both are set
      }
    },
    "workers": {                             // existing, unchanged: every worker process
      "total": 6,
      "active": 6
    },
    "server": {                              // NEW block: the API server
      "total": 4,                            // its processes, counted like workers (4 in one container)
      "active": 4,
      "processes_per_container": 4,          // the 4 gunicorn processes share one container
      "per_container": {                     // that container, whole
        "processor_available": 4,
        "processor_assigned": 4,
        "memory_total": 4294967296,          // 4 GiB
        "memory_available": 2684354560       // 2.5 GiB free
      }
    },
    "task_workers": {                        // NEW block: the task workers
      "total": 2,                            // its processes, counted like workers
      "active": 2,
      "processes_per_container": 1,          // a task worker has its container to itself
      "per_container": {                     // one of the two containers, whole
        "processor_available": 4,
        "processor_assigned": 4,
        "memory_total": 4294967296,          // 4 GiB
        "memory_available": 3221225472       // 3 GiB free
      }
    }
    // ... all other existing fields unchanged ...
  }
}
```

## What each figure means

All three components use the same four names, which the database block already used, and the database also reports `memory_assigned`. CPUs are counted as logical CPUs and memory is in bytes. Memory used is `memory_total − memory_available`.

| Figure | API server and task workers | Database |
|--------|-----------------------------|----------|
| `processor_available` | The CPUs the process can use: the smallest of the machine's CPU count, the container's CPU limit and the number of CPUs the process is pinned to, if it is pinned. | The CPUs Neo4j reports it can use. This also follows the container limit. |
| `processor_assigned` | The container's CPU limit. Empty when no limit is set. | The number of CPUs Neo4j's parallel query engine is set to use. Empty when the setting is left at its default. |
| `memory_total` | The container's memory limit, or the machine's memory when no limit is set. | The memory Neo4j reports: its container's memory limit, or the machine's memory when no limit is set. A Kubernetes memory request is not a limit. |
| `memory_available` | The memory still free under that limit, or the machine's free memory when no limit is set. | The free memory Neo4j reports, under the same limit or on the same machine. |
| `memory_assigned` | Not reported. | The memory Neo4j is set up to use: its heap (`server.memory.heap.max_size`) plus its page cache (`server.memory.pagecache.size`). Empty unless both are set. |

Two details matter when comparing figures:

- **Rounding.** A limit of 2.5 CPUs counts as 3 assigned CPUs, so the assigned figure never understates the limit, but as 2 usable CPUs, because 2.5 CPUs cannot keep a third CPU fully busy. A limit below 1 CPU still counts as 1 usable CPU. Neo4j rounds the limit up for its usable figure, so under a fractional limit the database's usable figure can be one higher than the other components'.
- **The database's assigned figure is not a hard ceiling.** It caps Neo4j's parallel query engine, not everything Neo4j does. The enterprise Helm chart presets set it to 4, 8 or 16 CPUs depending on size (infrahub-helm#93). The community chart and the compose file leave it unset.

## Where the API server and task-worker figures come from

Each process reads its figures from two sources:

- **The container limit**, from the Linux "cgroup" files where Docker or Kubernetes writes the limit it puts on a container, for example "this container may use 2 CPUs and 4 GB of memory".
- **The whole machine**, from the psutil library, for example "this machine has 18 CPUs and 64 GB".

When each one is used:

1. If a container limit is set, the limit is reported, because that is all Infrahub can use.
2. If no limit is set, the machine's figures are reported. Without a limit Infrahub can use the whole machine, so those figures are correct. This covers a laptop, bare metal, a VM, or a container started without limits.

Both are needed. Inside a container, psutil still sees the whole machine: on an 18-CPU machine with a container limited to 2 CPUs, psutil says 18. And without a limit, the cgroup files have no number to report.

Exceptions:

- **A limit is set but cannot be read.** The figure is reported as unknown (`null`) instead of the machine's figure, which could be far too high.
- **Assigned CPUs come only from the container limit.** With no limit, `processor_assigned` stays empty. It is never filled in from the machine, because it means "the limit someone set", and there is none.
- **A limit can be set on the container or on a group above it**, so every level is checked and the tightest limit wins.

Two things cannot be seen from inside a container:

- A limit set above the container's own view, for example on a Kubernetes node that itself runs in a container.
- Kubernetes CPU *requests*. A request reserves CPU for scheduling but does not limit it, so it is not reported.

A limit set only on a Kubernetes pod, when the container itself has none, is seen: on Kubernetes 1.37 with containerd, the pod's limit is also written on the container. Older Kubernetes versions were not checked.

## Per container

In `server` and `task_workers`, `per_container` holds the four figures of one of the component's containers, whole: the CPU and memory that every process in that container shares. `processes_per_container` is how many processes share that container. A component's total is **`per_container × active ÷ processes_per_container`**:

- A task worker runs one process per container, so `processes_per_container` is 1. In the example, 4 CPUs × 2 active ÷ 1 = 8 CPUs.
- The API server runs several processes in one container, and they share it. In the example, 4 CPUs × 4 active ÷ 4 = 4 CPUs.

Where `processes_per_container` comes from:

- An API server process started by gunicorn reports gunicorn's worker count, set with its `-w` option (4 by default in the Docker Compose file). The gunicorn worker class that Infrahub uses puts that count in each process's environment before the application loads.
- Every other process reports 1: a task worker, an API server started with `infrahub server start`, which runs a single process, and any other process that gunicorn did not start.
- Known gap: when an API server is started some other way with several processes in one container, for example with `uvicorn --workers 4` or with gunicorn and a different worker class, its processes report 1, so its total is overstated by its number of processes per container. Every way OpsMill ships Infrahub (the Docker Compose file, both Helm charts and the testcontainers stack) starts the API server through gunicorn with Infrahub's worker class.

Which container is reported:

- One reading stands for every container of the component, so every copy is assumed to run with the same settings. If copies differ, `per_container` shows one container's figures, not an average.
- When some readings miss a figure, the most complete one is used. `processes_per_container` always comes from the same reading as the figures.
- While a container runs fewer processes than `processes_per_container`, for example for the moment gunicorn takes to restart one, `active` is lower, so the total reads low until the process is back.

Every figure, and `processes_per_container`, is either `null` or a whole number sent as a JSON integer. A total worked out from them can have a fraction, for example 2 CPUs × 3 active ÷ 4 = 1.5 CPUs, so it needs decimal division, not whole-number division.

## When a figure is empty

`null` means "not measured" or "no limit set". It never means zero.

- **`processes_per_container` and every `per_container` figure are empty** when no active process of that component has a stored reading, or when the readings could not be read from the cache. `total` and `active` are still reported.
- **`processes_per_container` is reported even when every `per_container` figure is empty.** This happens when none of the readings of the component's active processes has any figure, for example because the CPU limit file and the memory limit file both exist but cannot be used.
- For the API server and task workers, the CPU and memory pairs show why a figure is missing:
  - `processor_available` set and `processor_assigned` empty: no CPU limit is set.
  - Both CPU figures empty: a CPU limit is set but could not be read. In the rare case that neither the machine's CPU count nor the CPUs the process is pinned to can be read, both are empty even without a limit.
  - Both memory figures empty: the memory limit, or the machine's memory, could not be read.
  - Only `memory_available` empty: the memory in use, or the machine's free memory, could not be read.
- **`database.system_info.processor_assigned` is empty** when the setting is left at its default, is not a positive number, or could not be read. A failed read is logged.
- **`database.system_info.memory_assigned` is empty** unless both the heap and the page cache are set, or when the settings could not be read. A failed read is logged. Without them, Neo4j works out its sizes from the memory it can see, which `memory_total` already reports. The Neo4j Docker image sets a 512 MiB page cache on its own when none is configured, so under Docker only the heap setting decides whether the figure is reported.
- **`database.system_info` is empty** when the database is not Neo4j.

## When the whole report is not produced

A failure in the new figures only empties those figures; the rest of the report is still produced. Several older parts of the report have no such protection, among them building the database block (including its CPU and memory figures) and reading the list of workers from the cache. A failure in any of them stops the whole daily report. None of them is new.

## Worker counts

- `workers.total` and `workers.active` are unchanged: they count every worker process, API server and task workers together.
- `server` and `task_workers` count their own processes the same way, so `server.total + task_workers.total` equals `workers.total`. The one exception is a process that stopped about two hours earlier: the keys that name its component have expired, but its 2-hour presence key has not yet. `workers` still counts it and the new blocks do not. This normally lasts at most the last 5 minutes or so before Infrahub forgets the process, and longer if its reads failed (a failed read stores nothing) or a long task kept it busy before the process stopped. It never affects `active`.
- `total` can stay above zero for up to two hours after the last process of a component stops. `active` drops to zero within 15 seconds.

## Readings and counts are separate

The figures come from a reading each process stores every 5 minutes, which is kept for 2 hours. Only the readings of the workers counted in `active` are used, so a stopped worker's reading is ignored although it stays in the cache. Beyond that:

- Each reading carries its own `processes_per_container`, so the figures do not depend on how many processes have stored a reading.
- A read that fails on every try stores nothing, so the process's last stored reading is kept, and can still be the one reported, until it expires 2 hours after it was stored. A process whose first read fails has no reading until a later read succeeds.
- A worker that never stores a reading is still counted in `total` and `active`.

## Compatibility

- No existing key is renamed, removed, retyped or changes meaning, and `payload_format` is unchanged (FR-008).
- Every new figure, and `processes_per_container`, can be `null` in any report, so the consumer must accept `null` for all of them.
- The new figures are also present when the deployment opted out of sending telemetry, but only in the copy stored locally. Nothing is sent.
