---
name: testing-against-real-data
description: >-
  Stands up a live Infrahub built from this worktree, loaded with the AI/DC solution's dataset,
  so a change can be exercised against realistic data at scale — tens of thousands of nodes,
  deep hierarchies, generators, artifacts, computed attributes, large diffs — instead of test
  fixtures. TRIGGER when: the user wants a change tried against a live app, real or realistic
  data, a big dataset, a large diff, or "at scale"; wants to reproduce something that only shows
  up on real data; wants a live Infrahub running to click through; or names the AI/DC solution.
  DO NOT TRIGGER when: the unit, component, or E2E suites already cover the behaviour → run
  those per AGENTS.md; the user only wants the dependencies up for a test run →
  `uv run invoke dev.deps`; the work is inside the ai-dc solution repository itself rather than
  in Infrahub.
compatibility: >-
  Requires Docker and Compose v2, uv, and a local clone of opsmill/infrahub-solution-ai-dc.
  Full build plus a fabric generation is a 20-30 minute cold start.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Testing against real data

## Introduction

The [AI/DC solution](https://github.com/opsmill/infrahub-solution-ai-dc) is a reference
implementation that builds AI data center fabrics with Infrahub generators, transforms, and
artifacts. A few dozen input objects expand into tens of thousands of nodes through a generator
cascade, so it is the quickest way to test an Infrahub change against data that behaves like a
customer's.

This skill gets that stack running **on the Infrahub built from the current worktree** and loaded
with data. The build is layered: your Infrahub image, then the solution image on top of it, and
the single most common failure is testing against a released Infrahub without noticing.

Cold start is expensive. Never rebuild without running Step 0 first.

`references/dev-stack-overlay.md` covers the alternative stack (this repo's dev compose, which
mounts the worktree at `/source` so backend edits need a restart rather than a rebuild).
`references/measuring.md` covers the solution's own test suites and frontend measurement. Don't
re-derive either.

## Step 0 — Find out what is already running

Rebuilding a stack that is already up wastes 20+ minutes. Check first, every time:

```bash
docker compose ls --filter name=infrahub-solution-ai-dc
curl -s -f -o /dev/null -w '%{http_code}\n' http://localhost:8000/api/config
```

Three outcomes:

- **Nothing running** → continue to Step 1.
- **Running** → confirm it is *your* build before trusting anything (Step 3's verification), then
  skip to Step 5 or Step 6. Data already loaded stays loaded.
- **Running but stale** (built before the change you want to test) → Step 2, then
  `uv run inv start`, which recreates the containers whose image changed. The database and its
  data survive; only `inv destroy` drops them.

When the user is iterating and a stack is already up, say what you found rather than rebuilding
on autopilot.

## Step 1 — Prerequisites

- The `python_sdk` submodule must be initialized (`git submodule update --init python_sdk`). A
  fresh worktree starts with an empty one.
- A clone of `opsmill/infrahub-solution-ai-dc`, outside this repository's tree, with
  `uv sync --all-packages` run in it. If the user has no clone, ask where to put it rather than
  choosing for them — it needs to outlive the session.

## Step 2 — Build your Infrahub into the solution image

Two layers. From the worktree, build Infrahub (`dev.build` tags it
`registry.opsmill.io/opsmill/infrahub:local`):

```bash
uv run invoke dev.build
```

Then from the solution clone, build the solution image on top of it:

```bash
export INFRAHUB_BASE_VERSION=local
uv run inv build
```

`INFRAHUB_BASE_VERSION` is what makes the stack yours. The solution otherwise derives the version
from its installed `infrahub-testcontainers` package, and that version picks both the base image
its Dockerfile extends and the tag its compose override runs. Without it you get the last
released Infrahub and the change under test is simply absent. Keep it exported for every later
command in the clone.

## Step 3 — Start and verify

```bash
uv run inv start
docker compose images
```

Every Infrahub service must show `opsmill/infrahub-solution-ai-dc:local`. If it shows a version
number, `INFRAHUB_BASE_VERSION` was not set and the stack is not testing your code. Stop and
rebuild rather than reporting results from it.

| Address | What |
|---|---|
| `http://localhost:8000` | API and UI |
| `http://localhost:4200` | Prefect, for generator and task runs |
| `http://localhost:7474` | Neo4j browser (Bolt on 7687) |
| `http://localhost:8001` | Infrahub MCP sidecar |

The stack seeds the development token `06438eb2-8019-4776-878c-0941b1f1d1ec` and the
`admin` / `infrahub` account.

## Step 4 — Load the solution

From the clone, in this order:

```bash
export INFRAHUB_ADDRESS="http://localhost:8000"
export INFRAHUB_API_TOKEN="06438eb2-8019-4776-878c-0941b1f1d1ec"

uv run inv load                              # schemas, menus, objects, repository
uv run infrahubctl repository list           # poll until the repository is in sync
uv run infrahubctl object load triggers.yml  # only after the sync completes
```

The order is not cosmetic. `triggers.yml` registers the node trigger rules and generator actions
that make one generator signal the next, and those references only resolve once the repository
has been imported. Loading it early fails or half-registers, and the symptom appears much later
as a generator cascade that stops after the first layer.

`inv load` skips the `data/` directory. Load it by hand when the test needs the sample operator
account or a second tenant:

```bash
uv run infrahubctl object load data/permissions.yml
uv run infrahubctl object load data/tenant-red.yml
```

## Step 5 — Generate a dataset at the size the test needs

Loading objects only creates design intent. The node count comes from running the generators.

In the UI: **Actions > Generator definitions > generate-fabric > Run**, then pick a fabric. One
trigger is enough — the fabric generator writes a checksum to each pod, which triggers the pod
generators in parallel, which do the same to their racks. Watch Prefect rather than guessing;
a full fabric takes several minutes and the computed-attribute cascade continues after the last
generator finishes.

Each of the four fabrics (one per vendor) is a similar unit of scale: Fabric-A is 6 super spines,
3 pods, 8 racks. To grow it, in rough order of effect:

- `amount_of_leafs` per rack (`objects/11_rack.yml`) — every leaf brings interfaces, cabling, and
  IP allocations, so this multiplies fastest.
- More racks and pods (`objects/11_rack.yml`, `objects/10_fabric.yml`).
- `generate-fabric` on more fabrics — independent, so it scales linearly and adds vendor variety.
- `amount_of_super_spines`, which mostly grows fabric-level cabling.
- `generate-tenant`, which adds routing and EVPN objects rather than devices.

**For a large diff rather than a large database**, generate on a branch: create it, make it
active, run the generator there, then open a proposed change against `main`. One fabric on an
empty branch reaches a five-figure node diff.

## Step 6 — Measure, don't assume

Before reporting any result, establish the size of what you are testing against:

```graphql
query {
  NetworkDevice { count }
}
```

A proposed change's diff summary gives added and updated node counts; `docker stats` gives the
memory picture during a cascade. Quote the numbers you measured. A claim like "tested at scale"
without a node count is not a result.

## Step 7 — Iterate

- **Backend change** → rebuild both layers (Step 2) and `uv run inv start`. Or switch to the dev
  stack in `references/dev-stack-overlay.md`, where a restart is enough.
- **Frontend change** → no rebuild. Run `cd frontend/app && pnpm dev`; the dev server on `:8080`
  calls the API at `http://localhost:8000` unconditionally. See `references/measuring.md`.
- **Restart** → `uv run inv restart`, or `--component task-worker` for one service. Restart the
  workers together with the server; a worker left on old code produces failures that look like
  data problems.
- **Teardown** → `uv run inv stop` keeps the data, `uv run inv destroy` removes the volumes.

## Failure modes that cost the most time

| Symptom | Cause | Fix |
|---|---|---|
| Change under test appears to have no effect | Stack is running a released Infrahub | `INFRAHUB_BASE_VERSION` was unset; verify with `docker compose images` (Step 3) |
| Repository stuck "syncing" | The `CoreRepository` object points at `/upstream`, which the compose override mounts from the clone | Check the mount before anything else |
| Generator cascade stops after the first layer | `triggers.yml` loaded before the repository finished syncing | Re-load it (Step 4) |
| Objects that should have been generated are missing | A generator failed on import; this surfaces as a failed task run, not a UI error | Check Prefect at `:4200` first |
| Every SDK import fails | The worktree is mounted over the image's `/source`, and an uninitialized `python_sdk` shadows the packaged SDK | `git submodule update --init python_sdk`, rebuild |
| Stack shape looks wrong after an Infrahub release | The released compose file is downloaded once and cached in the clone | `uv run inv download-compose-file --override` |

For the Enterprise stack, set `INFRAHUB_EDITION=enterprise` and re-fetch the compose file. That
one variable selects the compose stack, the base image the solution extends, and the name of the
image it builds, so the three cannot drift apart.
