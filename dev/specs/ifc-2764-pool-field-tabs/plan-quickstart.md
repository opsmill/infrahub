# Validating the remaining work

For exercising the *feature*, use the hand-written [quickstart.md](./quickstart.md) — 12 walkable
cases. This file is for validating the work this plan still describes.

> `quickstart.md` is not generated. Do not overwrite it.

## Prerequisites

```bash
cd ~/.claude-worktrees/infrahub-ple-ifc-2764-pool-kind-override
INFRAHUB_IMAGE_VER=local uv run invoke demo.start --wait      # source-mounted, so no rebuild
export INFRAHUB_ADDRESS=http://localhost:8000
export INFRAHUB_API_TOKEN=06438eb2-8019-4776-878c-0941b1f1d1ec
uv run infrahubctl schema load models/base models/examples/ipam_kind_override.yml --wait 30
uv run infrahubctl run models/examples/ipam_kind_override_data.py
cd frontend/app && pnpm start                                  # http://localhost:8080
```

Backend component tests need Docker: `DOCKER_HOST=unix:///Users/paul/.docker/run/docker.sock`
and `--no-cov`.

## The gate, in full

```bash
cd frontend/app
./node_modules/.bin/biome ci .          # exit 0
./node_modules/.bin/knip                # exit 0
./node_modules/.bin/betterer ci         # must stay at 186
./node_modules/.bin/vitest run          # currently 193 files / 1371 tests

cd ../..
uv run invoke format lint               # ruff, ty, mypy
DOCKER_HOST=unix:///Users/paul/.docker/run/docker.sock uv run pytest \
  backend/tests/component/core/resource_manager/ \
  backend/tests/component/core/test_relationship.py \
  backend/tests/component/graphql/resource_manager/ \
  backend/tests/component/graphql/queries/test_resource_pool.py --no-cov -q
```

Use the direct binaries: `pnpm exec` is unreliable in this environment. If `betterer ci` fails on
a stale hash rather than a count change, run plain `betterer` once and say so.

## Per-item validation

### Rebase (D1) — do this first

```bash
git fetch origin develop
git rev-list --left-right --count origin/develop...HEAD        # expect 0 behind afterwards
git log origin/develop -- frontend/app/src/shared/components/form/pool-selector.tsx
```

That last command matters: this branch **deleted** that file. If `develop` also touched it, resolve
by re-applying the deletion deliberately rather than accepting either side. After the rebase, run
the full gate **and** walk `quickstart.md` cases 1–6 in a browser: a clean gate does not prove the
form still renders.

### Availability harness (FR-023)

Each shape in [data-model.md](./data-model.md) is validated by reaching its matrix row **by hand**,
not only by a passing test:

| Shape | Reach it at | Expected |
|---|---|---|
| S1 single-implementation generic | its demo node's create form | pool offered, **no** type override |
| S2 `address` attribute | its demo node, **create** | pool offered; **edit** the same object → no pool |
| S3 Number attribute | its demo node's create form | pool offered, **neither** override |
| S4 object template | create an object from the template | value inherited, badged, and **not** submitted |

Then confirm every matrix row is asserted in vitest and pytest, including the rows where nothing
should be offered — those are the ones a refactor silently breaks.

### FR-017 attribute side (D3)

Depends on S2. With a pool-allocated `address` attribute on a saved object:

1. Reopen it. The **value** mode must be active, showing the allocated value.
2. The label must carry `data-testid="source-pool-badge"` naming the pool.
3. Switch mode, switch back, save. The object must be **byte-identical** (SC-008).

If step 1 or 2 fails, `getFieldDefaultValue` is misreporting provenance — fix it and add the
regression test. If both pass, record in spec.md why the suspect path is unreachable.

### e2e and docs (FR-024)

```bash
grep -rn "select_pool" tests/e2e/ | wc -l        # 8 call sites, ~10 files
```

`select_pool()` should absorb the tab click so call sites stay unchanged (D4). Call-site
assertions like `to_contain_text("Allocated by pool")` encode the old layout and must be revisited
one by one — the helper cannot absorb those.

Run the tutorial/guide e2e tests to regenerate documentation imagery, then review the produced
images: the published ones still show a pool button that no longer exists.

## Acceptance

- Every success criterion in [spec.md](./spec.md) → Measurable Outcomes is demonstrable.
- SC-005 specifically: every matrix row reachable by hand **and** asserted automatically.
- SC-008: open an object, look at both modes of a field, save → object unchanged.
- The full gate above is green, with pasted output rather than an assertion that it passed.
