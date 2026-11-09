# Worktrees skill: project-supplied setup-script contract

Date: 2026-06-25
Status: Approved (design)

## Problem

`dev/skills/worktrees/SKILL.md` is meant to be generic, but everything that
makes a fresh worktree *runnable* is project-specific: which env files to bring
over, which package managers to run, which submodules to init, how the dev stack
is scoped. Today the skill papers over this with prose ("the repo's
contribution guide names the actual commands"). That prose cannot be executed,
does not transfer cleanly to another repo, and silently rots.

Goal: keep `SKILL.md` portable — it should know *how to invoke* a per-project
setup step, never *what any given project needs* — and give Infrahub a concrete,
executable setup script that also unlocks running two worktrees concurrently.

## Two parts

1. A generic **contract** between the skill and any project (Section A).
2. Infrahub's **implementation** of that contract, including optional concurrent
   stacks via a port offset (Section B).

---

## Section A — Generic skill contract

The skill defines a contract and stops hard-coding project specifics.

### Discovery: convention path + frontmatter override

- Convention path: `.worktree-setup.sh` at the repo root.
- Override: an optional `worktree-setup:` field in `SKILL.md` frontmatter may
  point to a different path (relative to repo root). If present, it wins.
- Resolution order: frontmatter override → convention path → no script.

`SKILL.md` itself stays generic. The override field is the only project-aware
knob, and it is optional; most repos just drop the file at the convention path.

### Script contract: make-runnable only

After `git worktree add`, the skill runs the resolved script **inside the new
worktree**, passing context as environment variables:

- `WORKTREE_DIR` — absolute path of the new worktree
- `MAIN_DIR` — absolute path of the main worktree (where the skill was invoked)
- `BRANCH_NAME` — the branch checked out in the new worktree

The script is responsible for making the worktree runnable: submodules, env
files, dependency installs. It does **not** start the dev stack — running the
stack stays in the skill's prose. (Rationale: "make-runnable" is reusable across
projects; "start the stack" is not, and conflating them bloats the contract.)

Exit code: non-zero aborts with the script's output surfaced to the user.

### No-script fallback: offer to scaffold

If neither the override nor the convention path resolves to a file, the skill:

1. Inspects the repo (package managers present, gitignored env files,
   `.gitmodules`).
2. Offers to generate a starter `.worktree-setup.sh` from that inspection.
3. Lets the user review/edit it before first use.

The current generic prose (detect env files, run install command, init
submodules) becomes the **scaffolder's knowledge**, not a runtime path. After
scaffolding, subsequent runs take the normal discovery path. The skill therefore
still works on a fresh project out of the box, but converges on the executable
convention.

---

## Section B — Infrahub's `.worktree-setup.sh`

Implements the Section A contract for this repo. Guiding principle: **share
everything that cannot collide; isolate only the minimum that would.**

### Always done (no possible collision)

- `git submodule update --init --recursive`
  (`python_sdk`, `frontend/packages/schema-visualizer`) — must run before
  installs, since installers read submodule `pyproject.toml` / sub-workspace.
- `uv sync --all-groups`
- `pnpm install` (frontend workspace)

Worktrees never share `.venv/` or `node_modules/`, so installs are inherently
per-worktree; nothing to decide here.

### Env var sharing matrix

| Shared (inherit — cannot collide) | Isolated when concurrent (ports / identity) |
|---|---|
| `INFRAHUB_SECURITY_SECRET_KEY`, `INFRAHUB_USERNAME`, `INFRAHUB_PASSWORD`, `INFRAHUB_INITIAL_ADMIN_TOKEN` | `INFRAHUB_BUILD_NAME` (compose project name) |
| `INFRAHUB_TIMEOUT`, `INFRAHUB_DB_TYPE`, `INFRAHUB_PRODUCTION` | `INFRAHUB_SERVER_PORT` (8000), `INFRAHUB_METRICS_PORT` (8001) |
| `INFRAHUB_TRACE_ENABLE`, `INFRAHUB_TRACE_EXPORTER_TYPE` | `INFRAHUB_DB_PORT` (7687), neo4j-http (7474), rabbitmq (5672 / 15672), redis (6379), prefect (4200), db-backup (6362) |
| | derived addresses: `INFRAHUB_ADDRESS`, `INFRAHUB_INTERNAL_ADDRESS`, `PREFECT_API_URL`, `INFRAHUB_API_CORS_ALLOW_ORIGINS`, vite port (8080) |
| | storage: `INFRAHUB_STORAGE_LOCAL_PATH`, `INFRAHUB_GIT_GLOBAL_CONFIG_FILE` (see below) |

Note: `INFRAHUB_BUILD_NAME` already defaults to the worktree directory name
(`tasks/shared.py:56`), so distinct containers/volumes per worktree come for
free once a stack is brought up under a distinct name.

### Modes

**Default (shared, no flag).** Symlink the main `.envrc` into the worktree. Same
ports, same `BUILD_NAME` → same containers/volumes/DB. One stack up at a time,
zero port management. This is the cheap common case and matches today's
behaviour.

**`--isolated [--offset N]`.** Generate a worktree-local `.envrc` instead of
symlinking. It:

- `source`s a shared block from the main checkout (DRY) for every left-column
  var.
- Overrides each right-column var by `+N` (ports), sets `INFRAHUB_BUILD_NAME` to
  the worktree dir name, and rebuilds the derived addresses from the shifted
  ports.
- Points `INFRAHUB_STORAGE_LOCAL_PATH` and `INFRAHUB_GIT_GLOBAL_CONFIG_FILE` at
  a per-worktree directory (e.g. `infrahub-storage-<worktree>`), so two live
  stacks never clobber each other's repo checkouts/artifacts. (Decision:
  separate storage per worktree in isolated mode — matches separate DB volumes.)

`--offset` defaults to an auto-derived value if omitted (e.g. next free
multiple-of-100 among existing worktrees); an explicit value lets the user pin
it.

### Enabling changes (required for the offset to take effect)

The host ports are literal today, so the offset would be ignored without these.
Both are additive and default to current values, leaving the main checkout
unchanged. Both touch shared dev files ("Ask First" category) — call out in the
PR.

1. **`development/docker-compose.dev-override.yml`** — env-var-ize the literal
   host ports (e.g. `"${INFRAHUB_DB_PORT:-7687}:7687"`, same for 7474, 5672,
   15672, 6379, 4200). This makes the whole stack port-configurable from the
   `.envrc`, so no separate generated compose override file is needed.
2. **`frontend/app/vite.config.ts`** — read the dev server port from env
   (`port: Number(process.env.INFRAHUB_FE_PORT) || 8080`).

### `.envrc` refactor

Split the current `.envrc` into:

- A shared block containing the left-column vars (sourced by both the main
  checkout and any isolated worktree).
- The main `.envrc` sources the shared block and sets the right-column vars at
  their default (offset 0) values.

This keeps a single source of truth for shared values; isolated worktrees source
the same shared block and supply their own right-column overlay.

---

## Out of scope

- Starting/stopping the dev stack from the script (stays in skill prose).
- Auto-loading a second observability stack.
- Changing how the single shared-stack workflow behaves by default.

## Affected files

- `dev/skills/worktrees/SKILL.md` — rewrite the "Make the Worktree Runnable"
  and concurrent-stack sections around the contract; add the `worktree-setup:`
  frontmatter field and scaffold-offer flow.
- `.worktree-setup.sh` (new) — Infrahub's setup script.
- `development/docker-compose.dev-override.yml` — env-var-ize host ports.
- `frontend/app/vite.config.ts` — port from env.
- `.envrc` — split into shared block + main overlay.

## Risks

- Env-var-izing dev-override ports and the `.envrc` split are shared-dev-file
  changes; verify `invoke dev.start` is byte-for-byte equivalent at offset 0.
- Auto-offset collision if two worktrees pick the same N; deterministic
  derivation + an explicit `--offset` escape hatch mitigates this.
- direnv must `direnv allow` the generated `.envrc` in each worktree (document
  in the script output).
