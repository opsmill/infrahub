# Measuring against the loaded stack

## Running the solution's own test suites on your build

The solution's unit tests need no deployment:

```bash
uv run inv test-unit
```

Its integration suite starts a throwaway stack through testcontainers and resolves which image to
run from `INFRAHUB_BASE_VERSION`, the same variable that drives the compose stack. Build under a
tag, then run against it:

```bash
docker tag registry.opsmill.io/opsmill/infrahub:local registry.opsmill.io/opsmill/infrahub:dev-mybranch
export INFRAHUB_BASE_VERSION=dev-mybranch
uv run inv build
uv run inv test-integration        # --tier full for the extended tier
```

The tag cannot be the literal `local` here: testcontainers treats that as a sentinel and
re-resolves it, so the suite rejects it up front rather than running the wrong image. Any other
tag works, which is why the re-tag exists. The suite also stops immediately, naming the command
to run, when the image it needs was never built.

## Measuring a frontend change

The Vite dev server serves the worktree, so a frontend change can be compared against its own
baseline on the live instance without rebuilding anything:

```bash
cd frontend/app && pnpm dev
```

It listens on `:8080` and, in dev mode, calls the API at `http://localhost:8000`
unconditionally — no proxy or environment variable to configure, and no way to point it
elsewhere without editing `frontend/app/src/shared/config/config.ts`.

For a before/after comparison, set the change aside and let hot reload swap it in place. The
stash stack is shared across worktrees, so tag the entry and restore it by SHA rather than
popping blind:

```bash
git stash push -u -m "ai-dc-perf-ab" -- frontend/app/src
git stash list --format='%H %gs' | head -3     # capture the SHA of your entry
# exercise the page, take the measurement
git stash apply <sha>
```

Path exclusions (`':(exclude)<path>'`) let you set aside one part of a change and keep another,
which is how you measure an old rendering cost while keeping a fix that stops the page crashing.

Two habits make these measurements trustworthy:

- Keep the browser tab focused. Browsers throttle timers in hidden tabs, so a paginated load
  stalls and every timing is wrong.
- Compare like for like. Reload between runs and let the same number of pages load before
  measuring; a partially loaded page always looks faster.

## Reporting

Local timings do not transfer to CI — local database latency inflates them, so never extrapolate
local seconds into predicted CI savings. Report what you measured, on what dataset size, on which
machine.
