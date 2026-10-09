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
        "memory_available": 47034888192      // existing: free bytes
      }
    },
    "workers": {                             // existing, unchanged: every worker process
      "total": 6,
      "active": 6
    },
    "server": {                              // NEW block: the API server
      "total": 4,                            // its processes, counted like workers (4 in one container)
      "active": 4,
      "per_worker": {                        // each process gets a quarter of the container
        "processor_available": 1.0,          // 4 CPUs / 4 processes
        "processor_assigned": 1.0,
        "memory_total": 1073741824,          // 4 GiB / 4
        "memory_available": 671088640        // 2.5 GiB free / 4
      }
    },
    "task_workers": {                        // NEW block: the task workers
      "total": 2,                            // its processes, counted like workers
      "active": 2,
      "per_worker": {                        // a task worker has its container to itself
        "processor_available": 4.0,
        "processor_assigned": 4.0,
        "memory_total": 4294967296,          // 4 GiB
        "memory_available": 3221225472       // 3 GiB free
      }
    }
    // ... all other existing fields unchanged ...
  }
}
```

## What each figure means

All three components use the same four names, which the database block already used. CPUs are counted as logical CPUs and memory is in bytes. Memory used is `memory_total − memory_available`.

| Figure | API server and task workers | Database |
|--------|-----------------------------|----------|
| `processor_available` | The CPUs the process can use: the smallest of the machine's CPU count, the container's CPU limit and the number of CPUs the process is pinned to, if it is pinned. | The CPUs Neo4j reports it can use. This also follows the container limit. |
| `processor_assigned` | The container's CPU limit. Empty when no limit is set. | The number of CPUs Neo4j's parallel query engine is set to use. Empty when the setting is left at its default. |
| `memory_total` | The container's memory limit, or the machine's memory when no limit is set. | The memory Neo4j reports. |
| `memory_available` | The memory still free under that limit, or the machine's free memory when no limit is set. | The free memory Neo4j reports. |

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

- A limit set only on a Kubernetes pod, when the container itself has none.
- Kubernetes CPU *requests*. A request reserves CPU for scheduling but does not limit it, so it is not reported.

## Per worker

In `server` and `task_workers`, `per_worker` is one worker's share of its container. A component's total is **`per_worker × active`**:

- A task worker runs one process per container, so its share is the whole container. In the example, 4.0 CPUs × 2 workers = 8 CPUs.
- The API server runs several processes in one container (4 by default), and they share it. Each process gets a part, so the figures are divided by the number of processes. In the example, 1.0 CPU × 4 processes = 4 CPUs.

How the share is worked out:

- One reading stands for every container of the component, so every copy is assumed to run with the same settings. If copies differ, `per_worker` shows one container's figures, not an average.
- When some readings miss a figure, the most complete one is used.
- CPU shares keep two decimals. A whole number is sent as an integer (`2`, not `2.0`), because the telemetry endpoint checks the checksum by writing the data out again in JavaScript, which cannot tell the two apart. Memory shares are whole bytes, rounded down.

## When a figure is empty

`null` means "not measured" or "no limit set". It never means zero.

- **Every `per_worker` figure is empty** when no process of that component has stored a usable reading, or when reading them from the cache failed.
- For the API server and task workers, the CPU and memory pairs show why a figure is missing:
  - `processor_available` set and `processor_assigned` empty: no CPU limit is set.
  - Both CPU figures empty: a CPU limit is set but could not be read. In the rare case that neither the machine's CPU count nor the CPUs the process is pinned to can be read, both are empty even without a limit.
  - Both memory figures empty: the memory limit, or the machine's memory, could not be read.
  - Only `memory_available` empty: the memory in use, or the machine's free memory, could not be read.
- **`database.system_info.processor_assigned` is empty** when the setting is left at its default, is not a positive number, or could not be read. A failed read is logged.
- **`database.system_info` is empty** when the database is not Neo4j.

## When the whole report is not produced

A failure in the new figures only empties those figures; the rest of the report is still produced. Several older parts of the report have no such protection, among them building the database block (including its CPU and memory figures) and reading the list of workers from the cache. A failure in any of them stops the whole daily report. None of them is new.

## Worker counts

- `workers.total` and `workers.active` are unchanged: they count every worker process, API server and task workers together.
- `server` and `task_workers` count their own processes the same way, so `server.total + task_workers.total` equals `workers.total`. The one exception is a process that stopped about two hours earlier: the keys that name its component have expired, but its 2-hour presence key has not yet. `workers` still counts it and the new blocks do not. This normally lasts the last 15 minutes or so before Infrahub forgets the process, and longer if Infrahub could not refresh its branches, or a long task kept it busy, before the process stopped. It never affects `active`.
- `total` can stay above zero for up to two hours after the last process of a component stops. `active` drops to zero within 15 seconds.

## Readings and counts are separate

The figures come from a reading each process stores next to its heartbeat, which expires after the same 15 seconds. They are not matched against the active workers, so:

- A process that has not stored a reading yet is not counted when its container is divided, so the share reads high until it does. Each process stores a reading when it starts, so this is brief.
- A worker that never stores a reading is still counted in `total` and `active`.
- The container name used to group readings is never sent.

## Compatibility

- No existing key is renamed, removed, retyped or changes meaning, and `payload_format` is unchanged (FR-008).
- Every new figure can be `null` in any report, so the consumer must accept `null` for all of them.
- The new figures are also present when the deployment opted out of sending telemetry, but only in the copy stored locally. Nothing is sent.
