# The dev stack with a solution overlay

The main workflow runs the solution's own compose stack, where Infrahub is baked into the image
and a backend change means rebuilding both layers. This repository's dev stack mounts the
worktree at `/source` in the server, workers, and task manager instead, so a backend edit needs
only a container restart.

Take this path when rebuilds are too slow for the loop you are in, or when you need the
observability services. Everything else — loading the solution, generating the dataset,
measuring — is unchanged.

| | Solution stack (default) | Dev stack (here) |
|---|---|---|
| Compose files | Released stack downloaded by the solution, plus its override | `development/docker-compose*.yml` |
| Infrahub code | Baked in; rebuild to change it | Mounted at `/source`; restart to change it |
| Solution wiring | Already in the solution's override | You write the overlay below |
| Also available | MCP sidecar, Prefect, Neo4j browser and Bolt | Observability stack, behind its own profiles |
| Service names | `infrahub-server`, `task-worker`, `task-manager` | `server`, `task-worker`, `task-manager` |

## Build both images first

Same as the main workflow: `uv run invoke dev.build` here, then
`INFRAHUB_BASE_VERSION=local uv run inv build` in the solution clone. The dev stack still runs
the *solution* image, because the plain Infrahub image has no `infrahub_solution_ai_dc` package
and every generator fails on import without it.

## Write the overlay

The dev stack knows nothing about the solution, so add what the solution's own
`docker-compose.override.yml` provides: the environment it needs, the clone mounted at
`/upstream` (the location its `CoreRepository` object points at), and its `src/` for live edits
to the solution package.

`development/docker-compose.ai-dc.yml` is untracked and works. Replace `<AI_DC_CLONE>` with the
absolute path to the clone, for example `/home/you/src/infrahub-solution-ai-dc`; a relative path
resolves against the compose project directory rather than the repository root, so an absolute
one avoids a mount that silently points somewhere else.

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

Keep it in sync with the solution's `docker-compose.override.yml`; those settings are copied from
it, and it is the file that changes when the solution needs a new one.

## Start it

Pin the compose project name so later commands stay readable — it otherwise defaults to the
sanitized worktree directory name.

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

- `--profile dev`: `server` and the workers only exist under the `dev` and `demo` profiles.
  Without a profile you get the dependencies and nothing else. The observability services sit
  behind profiles of their own, so add `--profile debug` for Prometheus, Grafana, and the
  exporters, and `--profile trace` for Tempo.
- `--pull never`: the dev stack sets `pull_policy: always`, which fails on a tag that only
  exists locally.
- The `local-build` files: they are what mount the worktree at `/source`. Drop them and you are
  running the code baked into the image instead.

## Day-two

```bash
docker compose -p ai-dc restart server task-worker
docker compose -p ai-dc logs -f server task-worker
docker compose -p ai-dc down -v --remove-orphans
```
