# Testing against the AI/DC solution

> Part of: `dev/guides/` | Related: [Backend testing](../knowledge/backend/testing.md), [Writing E2E tests](frontend/writing-e2e-tests.md)

The [AI/DC solution](https://github.com/opsmill/infrahub-solution-ai-dc) is a reference
implementation that builds AI data center fabrics out of Infrahub generators, transforms, and
artifacts. For Infrahub development it is the quickest way to get a realistic dataset: a few dozen
input objects expand into tens of thousands of nodes through a generator cascade, with computed
attributes, artifacts, resource pools, and a hierarchy several levels deep.

Use it when unit, component, and E2E fixtures are too small or too synthetic to show the behavior
you are working on:

- Performance and scaling work: query timings, diff size, memory, pagination.
- Anything that traverses a deep hierarchy (fabric, pod, rack, device, interface).
- Generators, transforms, artifacts, computed attributes, and the trigger rules that chain them.
- Branch and proposed-change flows over a large diff.
- Frontend rendering at a scale the demo data never reaches.

The solution repository documents how to run itself against a released Infrahub. This guide covers
the part it does not: pointing it at an Infrahub you built from this repository, and working against
it while you change Infrahub.

## Prerequisites

- Docker and Docker Compose v2. A full generator run needs noticeably more memory than the standard
  demo stack, between Neo4j and the Infrahub containers, so give Docker as much as you can spare.
- A clone of the solution repository, somewhere durable and outside this repository's tree:

  ```bash
  git clone git@github.com:opsmill/infrahub-solution-ai-dc.git
  cd infrahub-solution-ai-dc && uv sync --all-packages
  ```

- An initialized `python_sdk` submodule on the Infrahub side. A fresh worktree starts with an empty
  one, and an empty directory mounted over the image's packaged SDK breaks every import of it:

  ```bash
  git submodule update --init python_sdk
  ```

## Pick a stack

Two stacks can run the solution. They differ in where the Infrahub code comes from.

| | Solution stack (path A) | This repo's dev stack (path B) |
|---|---|---|
| Compose files | Released stack downloaded by the solution, plus its own override | `development/docker-compose*.yml` from this repo |
| Infrahub code | Baked into the image; rebuild to change it | Mounted from the worktree at `/source`; restart to change it |
| Solution wiring | Already in the solution's override | You write an overlay |
| Also published | MCP sidecar, Prefect, Neo4j browser and Bolt | Observability profile (Prometheus, Grafana, Tempo) |
| Service names | `infrahub-server`, `task-worker`, `task-manager` | `server`, `task-worker`, `task-manager` |

Path A is the default: less to maintain, and the solution owns the wiring. Take path B when image
rebuilds are too slow for the loop you are in, or when you need the observability stack.

Both paths build the same two layered images. The solution image installs the
`infrahub_solution_ai_dc` package that its generators import, so the task workers need it; running
plain Infrahub images makes every generator fail on import.

### Path A: the solution stack on your Infrahub build

Build the Infrahub image from the worktree. `dev.build` tags it
`registry.opsmill.io/opsmill/infrahub:local`:

```bash
uv run invoke dev.build
```

Then, from the solution clone, build the solution image on top of it and start the stack:

```bash
export INFRAHUB_BASE_VERSION=local
uv run inv build
uv run inv start
```

`INFRAHUB_BASE_VERSION` is what makes this your build. The solution otherwise derives the Infrahub
version from its installed `infrahub-testcontainers` package, and that version selects both the base
image its `Dockerfile` extends and the tag its compose override runs. Setting it explicitly redirects
both at your local image. Without it the stack runs the last released Infrahub without saying so, and
whatever you are testing is not in it.

Confirm what actually started, from the solution clone:

```bash
docker compose images
```

Every Infrahub service should show `opsmill/infrahub-solution-ai-dc:local`.

| Address | What |
|---|---|
| `http://localhost:8000` | API and UI |
| `http://localhost:4200` | Prefect, for task runs and failures |
| `http://localhost:7474` | Neo4j browser (Bolt on 7687) |
| `http://localhost:8001` | Infrahub MCP sidecar |

The stack seeds the well-known development token `06438eb2-8019-4776-878c-0941b1f1d1ec` and the
`admin` / `infrahub` account.

The released compose file is downloaded once and cached as `docker-compose.yml` in the clone. It is
not refreshed on later starts, so after an Infrahub release changes the shape of the stack, re-fetch
it:

```bash
uv run inv download-compose-file --override
```

For the Enterprise stack, set `INFRAHUB_EDITION=enterprise` before the commands above and re-fetch
the compose file. That one variable selects the compose stack, the base image the solution extends,
and the name of the image it builds, so the three cannot drift apart.

### Path B: this repo's dev stack with a solution overlay

The dev stack mounts the worktree at `/source` in the server, workers, and task manager, so backend
edits need a container restart rather than an image rebuild. It knows nothing about the solution, so
you add what the solution's own override provides: the environment it needs, the clone mounted
at `/upstream` (the location its `CoreRepository` object points at), and its `src/` for live edits to
the solution package.

Build both images first, exactly as in path A (`uv run invoke dev.build`, then
`INFRAHUB_BASE_VERSION=local uv run inv build` from the clone).

Write the overlay somewhere durable — `development/docker-compose.ai-dc.yml` is untracked and works:

```yaml
---
x-ai-dc-env: &ai_dc_env
  INFRAHUB_GIT_USER_NAME: "infrahub"
  INFRAHUB_GIT_EMAIL: "no-reply@opsmill.com"
  INFRAHUB_GIT_USE_EXPLICIT_MERGE_COMMIT: "true"
  INFRAHUB_TIMEOUT: "180"
  # The fabric/pod/rack hierarchy traverses more levels than the 30s default allows.
  INFRAHUB_DB_PATH_TRAVERSAL_QUERY_TIMEOUT: "75"

services:
  server:
    environment:
      <<: *ai_dc_env
  task-worker:
    environment:
      <<: *ai_dc_env
    volumes:
      - <AI_DC_CLONE>:/upstream
      - <AI_DC_CLONE>/src:/opt/local/src
```

Keep the overlay in sync with the solution's `docker-compose.override.yml`; the settings above are
copied from it, and it is the file that changes when the solution needs a new one.

Start the stack with the solution image substituted for the Infrahub one. Pin the compose project
name so day-two commands stay readable — it otherwise defaults to the sanitized worktree directory
name:

```bash
INFRAHUB_BUILD_NAME=ai-dc \
IMAGE_NAME=opsmill/infrahub-solution-ai-dc IMAGE_VER=local \
docker compose -p ai-dc --profile dev \
  -f development/docker-compose-deps.yml \
  -f development/docker-compose-database-neo4j.yml \
  -f development/docker-compose-observability.yml \
  -f development/docker-compose.yml \
  -f development/docker-compose.default.yml \
  -f development/docker-compose.local-build.yml \
  -f development/docker-compose.local-build-deps.yml \
  -f development/docker-compose.ai-dc.yml \
  up -d --pull never
```

Three parts of that command are required:

- `--profile dev`: `server` and the workers only exist under the `dev` and `demo` profiles. Without
  a profile you get the dependencies and nothing else.
- `--pull never`: the dev stack sets `pull_policy: always`, which fails on a tag that only exists
  locally.
- The `local-build` files: they are what mount the worktree at `/source`. Drop them and you are
  running the code baked into the image instead.

## Load the solution

Point `infrahubctl` at the stack and load, in this order, from the solution clone:

```bash
export INFRAHUB_ADDRESS="http://localhost:8000"
export INFRAHUB_API_TOKEN="06438eb2-8019-4776-878c-0941b1f1d1ec"

uv run inv load                                 # schemas, menus, objects, repository
uv run infrahubctl repository list               # wait until the repository is in sync
uv run infrahubctl object load triggers.yml      # only after the sync completes
```

The order matters. `triggers.yml` registers the node trigger rules and generator actions that make
one generator run signal the next, and those references only resolve once the repository has been
imported. Loading it early fails or, worse, half-registers.

`inv load` deliberately skips the `data/` directory. Load it by hand when you want the sample
operator account and the day-two tenant, both of which are useful for exercising permissions and
incremental changes:

```bash
uv run infrahubctl object load data/permissions.yml
uv run infrahubctl object load data/tenant-red.yml
```

## Scale the dataset

Loading the objects only creates the design intent. The node count grows when the generators run.

In the UI, go to **Actions > Generator definitions > generate-fabric**, click **Run**, and select a
fabric. One trigger is enough: the fabric generator writes a checksum to each of its pods, which
triggers the pod generators in parallel, which do the same to their racks. Watch it in Prefect rather
than guessing; on an M-series laptop a full fabric takes several minutes, and the computed-attribute
cascade continues after the last generator finishes.

As shipped, each of the four fabrics (one per vendor) carries a similar load: Fabric-A has 6 super
spines, 3 pods, and 8 racks. That is the unit of scale — everything below is derived from it.

Levers, in rough order of effect:

- Leaf count per rack (`amount_of_leafs` in `objects/11_rack.yml`). Every leaf adds its interfaces,
  cabling, and IP allocations, so this grows the node count fastest.
- Rack and pod count (`objects/11_rack.yml`, `objects/10_fabric.yml`).
- Running `generate-fabric` on more than one fabric. Fabrics are independent, so this scales linearly
  and also gets you multi-vendor rendering.
- Super spine count (`amount_of_super_spines`), which mostly grows the fabric-level cabling.
- Overlay tenants and segments through `generate-tenant`, which adds routing and EVPN objects rather
  than more devices.

To produce a large **diff** rather than a large database, do the generation on a branch: create the
branch, make it active, run the generator there, then open a proposed change against `main`. A single
fabric on an empty branch is enough to reach a five-figure node diff.

Measure what you built instead of assuming. Node counts come from GraphQL:

```graphql
query {
  NetworkDevice { count }
}
```

The proposed change's diff summary gives the added and updated node counts, and `docker stats` gives
the memory picture while a generator cascade runs.

## Day-two operations

Path A, from the solution clone (`INFRAHUB_BASE_VERSION` must stay exported):

```bash
uv run inv restart                 # or: uv run inv restart --component task-worker
uv run inv stop
uv run inv destroy                 # removes volumes; the loaded data goes with them
```

After a backend change, rebuild both layers and bring the stack back up; compose recreates the
containers whose image changed:

```bash
uv run invoke dev.build            # in the Infrahub worktree
uv run inv build && uv run inv start   # in the solution clone
```

Path B, with the project name pinned as above:

```bash
docker compose -p ai-dc restart server task-worker
docker compose -p ai-dc logs -f server task-worker
docker compose -p ai-dc down -v --remove-orphans
```

Restart the workers together with the server. They run the same Infrahub code from the same mount,
and a worker left on the old code produces failures that look like data problems.

## Run the solution's own test suites against your build

The solution's unit tests need no deployment:

```bash
uv run inv test-unit
```

Its integration suite starts a throwaway stack through testcontainers, and resolves which image to
run from `INFRAHUB_BASE_VERSION` — the same variable that drives the compose stack. Build under a
tag, then run against it:

```bash
docker tag registry.opsmill.io/opsmill/infrahub:local registry.opsmill.io/opsmill/infrahub:dev-mybranch
export INFRAHUB_BASE_VERSION=dev-mybranch
uv run inv build
uv run inv test-integration        # add --tier full for the extended tier
```

The tag cannot be the literal `local` here: testcontainers treats that as a sentinel and re-resolves
it, so the suite rejects it up front rather than running the wrong image. Any other tag works, which
is why the re-tag above exists. The suite also stops immediately, naming the command to run, when
the image it needs was never built.

## Measure a frontend change on a large dataset

The dev server serves the worktree source, so a frontend change can be compared against its own
baseline on a live instance without rebuilding anything. Run Vite from the worktree while either
stack is up:

```bash
cd frontend/app && pnpm dev
```

It listens on `http://localhost:8080` and, in dev mode, calls the API at `http://localhost:8000`
unconditionally — no proxy or environment variable to configure, but also no way to point it
somewhere else without editing `frontend/app/src/shared/config/config.ts`.

For a before/after comparison, stash the change and let hot reload swap it in place:

```bash
git stash push -u -m "perf A/B" -- frontend/app/src
# exercise the page, take the measurement
git stash pop
```

Path exclusions (`':(exclude)<path>'`) let you stash one part of a change and keep another, which is
how you measure an old rendering cost while keeping a fix that prevents the page from crashing.

Two habits make these measurements trustworthy:

- Keep the tab focused. Browsers throttle timers in hidden tabs, so a paginated load stalls and every
  timing is wrong.
- Compare like for like. Reload between runs, and let the same number of pages load before measuring;
  a partially loaded page always looks faster.

## Gotchas

- The image is only as fresh as the last build. After switching branches, rebuild both layers before
  concluding anything about behavior.
- Keep the clone, the overlay, and any measurement scripts outside ephemeral scratch directories.
  Rebuilding this environment costs more than the investigation that needed it.
- The `CoreRepository` object points at `/upstream`. If the repository never leaves "syncing", check
  that mount before anything else.
- A generator that fails on import shows up as a failed task run in Prefect, not as an error in the
  UI. Check Prefect first when objects that should have been generated are missing.
- Path B mounts the worktree over the image's `/source`, which includes `python_sdk`. An
  uninitialized submodule shadows the SDK packaged in the image, and every import of it fails.
