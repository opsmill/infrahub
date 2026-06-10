# Dockerfile node-stage restructure

Date: 2026-06-10
Branch: `bab-pnpm-workspaces` (new commits, no separate branch)
Scope: `development/Dockerfile` node stages, `frontend/app/package.json`, `development/docker-compose.yml`, `.dockerignore`

## Problem

The node side of `development/Dockerfile` has structural defects, confirmed by a
verified multi-agent review of the file against the repo:

1. The `# STAGE : Documentation` banner (lines 60-62) has no `FROM` — the docs
   build runs inside the `frontend` stage. The two independent builds are
   serialized, and any frontend change forces a full docs `npm install` +
   Docusaurus rebuild. Line 109's `COPY --from=frontend /docs/build/` only
   works because of this accidental fusion.
2. Docs build inputs (`backend/infrahub/config.py`, `models/`, python_sdk
   examples, the entire `development/` directory) are copied *before*
   `npm install`, so editing the Dockerfile itself re-runs the install. Two of
   the four copies (`config.py`, python_sdk examples) are referenced nowhere in
   the docs sources.
3. `node:24-slim` floats while the Python base pins `ARG PYTHON_VER=3.13.11`.
4. `corepack prepare pnpm@10` is deprecated upstream (corepack removed from
   Node 25+), floats on the 10.x line, and is dead weight: the corepack shim
   resolves `packageManager: pnpm@10.33.2` from `frontend/package.json` anyway.
5. Full `frontend/packages/ui/` sources are copied before `pnpm install`, so
   any UI-package edit re-runs the whole install (the workspace member only
   needs its `package.json` at install time).
6. `npm install --omit=dev` treats `docs/package-lock.json` as advisory.
7. `pnpm install --prod` only works because the vite build toolchain is
   misfiled in `dependencies` — moving any plugin to `devDependencies` (the
   conventional place) would break the Docker build while local builds pass.
8. In the backend stage, `COPY --from=frontend` (lines 104, 109) precedes the
   cached `uv sync` layer, so every frontend/docs edit re-runs `uv sync`.
9. `pnpm store prune` / `npm cache clean --force` delete cache written in
   earlier layers — strictly dead work in a stage that never ships.
10. `ARG CI_ARG` / `ENV CI=$CI_ARG` has inverted semantics: compose passes
    `${CI:-0}` and ci-info treats `"0"` as truthy, so dev builds run in CI
    mode while the real CI workflow never passes `CI_ARG` at all.
11. `.dockerignore` misses `frontend/**/dist`, `frontend/**/test-results`,
    `frontend/**/coverage`, so stale local artifacts bust the source-COPY
    layer cache.

Out of scope (explicit decision): adding a buildx cache backend
(`cache-from`/`cache-to`) to `ci-docker-image.yml`. Without it, CI builds stay
fully cold and the cache mounts below only benefit local/compose builds — same
limitation as the existing uv cache mount.

## Design

### Stage topology (approach: deeper restructure, chosen over minimal in-place edits)

The single fused node stage becomes five stages:

```text
node-base          FROM docker.io/node:${NODE_VER}-slim    (ARG NODE_VER=24.15.0)
                   RUN npm install -g pnpm@10.33.2         (replaces corepack;
                                                            keep in sync with
                                                            packageManager in
                                                            frontend/package.json)

frontend-deps      FROM node-base
                   WORKDIR /frontend
                   COPY frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml
                   RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm fetch
                   COPY frontend/package.json frontend/app/package.json
                        frontend/packages/ui/package.json   (manifests only)
                   COPY frontend/packages/schema-visualizer/  (file: dep —
                                                            sources required
                                                            at install time)
                   RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
                       pnpm install --frozen-lockfile --offline

frontend-build     FROM frontend-deps
                   COPY frontend/packages/ui/ frontend/app/
                   WORKDIR /frontend/app
                   RUN pnpm build

docs-deps          FROM node-base
                   ENV DOCS_IN_APP=1
                   WORKDIR /docs
                   COPY docs/package.json docs/package-lock.json
                   RUN --mount=type=cache,target=/root/.npm npm ci --omit=dev

docs               FROM docs-deps
                   COPY models/ development/deploy.tf development/k8s/ docs/
                   RUN npm run build
```

pnpm's store directory is pointed at the cache mount via
`RUN pnpm config set store-dir /pnpm/store --global` in `node-base`.
The store sits on a different filesystem than `node_modules`, so pnpm copies
instead of hardlinking — accepted; downloads are still skipped.

Layer-cache properties this buys:

- `pnpm fetch` keys on the lockfile only: a `package.json` edit re-runs the
  install offline with zero downloads.
- The install keys on manifests only: app or `packages/ui` source edits re-run
  only `pnpm build`.
- Frontend and docs chains are independent below `node-base`: BuildKit builds
  them in parallel; a frontend edit never invalidates docs layers.
- Dead copies (`backend/infrahub/config.py`, python_sdk examples) are removed;
  `development/` narrows to `deploy.tf` + `k8s/` — the only paths the docs
  raw-load.
- `pnpm store prune` and `npm cache clean --force` are dropped (caches live in
  mounts, never in layers).
- `ARG CI_ARG` / `ENV CI` is deleted (see compose change below). The only flag
  that mattered, `--frozen-lockfile`, is already explicit.

### Backend stage

The artifact imports move below the dependency layer, and the stage references
are updated:

```text
COPY uv.lock pyproject.toml ... /source/                     (unchanged)
RUN --mount=...uv... uv sync --frozen --no-dev
    --no-install-project --no-install-workspace              (unchanged)
COPY --from=frontend-build /frontend/app/dist/ /opt/infrahub/frontend/app/dist
COPY --from=docs /docs/build/ /opt/infrahub/docs/build
COPY . ./
RUN --mount=...uv... uv sync --frozen --no-dev               (unchanged)
```

Frontend/docs edits no longer re-run the `uv sync` dependency layer, and the
Python dependency build runs in parallel with the node stages.

### frontend/app/package.json

Eight build-toolchain packages move from `dependencies` to `devDependencies`
(verified: each is consumed only by `vite.config.*` / the build pipeline,
never imported by app source):

`@rolldown/plugin-babel`, `@tailwindcss/vite`, `@vitejs/plugin-react`,
`babel-plugin-react-compiler`, `tailwindcss`, `vite`,
`vite-plugin-monaco-editor-esm`, `vite-plugin-svgr`.

Consequently `pnpm fetch` and `pnpm install` in the Dockerfile run **without**
`--prod` (the build needs dev deps). Trade-off accepted: the intermediate deps
stage also installs test tooling (vitest, playwright packages — no browser
downloads); the shipped image is unchanged. `pnpm-lock.yaml` is regenerated by
the move and committed with it.

### Supporting files

- `development/docker-compose.yml`: delete `CI_ARG: ${CI:-0}` build args
  (both occurrences) in the same commit as the Dockerfile change, otherwise
  BuildKit warns about an unconsumed build-arg.
- `.dockerignore`: add `frontend/**/dist`, `frontend/**/test-results`,
  `frontend/**/coverage` (safe: schema-visualizer's `dist/` is untracked
  build output, not checked in).
- `tasks/container_ops.py` / CI workflows: untouched. `NODE_VER` gets a pinned
  Dockerfile default only; plumbing it through invoke like `PYTHON_VER` would
  reintroduce floating versions (the `PYTHON_VER=3.13` default in
  `tasks/shared.py` already floats — known, not fixed here).
- Towncrier `housekeeping` changelog fragment.

### Risks

- `pnpm fetch` + the `file:` schema-visualizer dep is the one new mechanism:
  `fetch` populates the store from the lockfile; the `file:` dep resolves from
  the copied sources at install time. If `--offline` trips on the `file:`
  edge case, fallback is dropping `--offline` from the install — the cache
  mount keeps it cheap and layer keying is unchanged.
- `npm ci` fails on lockfile drift by design; if `docs/package-lock.json` is
  stale, regenerate it rather than reverting to `npm install`.
- Stage renames are safe: every consumer (`ci-docker-image.yml`, compose,
  invoke tasks) targets `backend` only.

## Verification

1. `pnpm install && pnpm build` in `frontend/app` after the dep reshuffle,
   plus `pnpm test`.
2. Iterate with `docker build --target frontend-build` / `--target docs`.
3. One full `docker build --target backend`.
4. Cache proof: touch a file under `frontend/app/src`, rebuild `backend`,
   confirm the docs layers and both `uv sync` layers report `CACHED`.

## Delivery

Commits on `bab-pnpm-workspaces`:

1. `frontend/app/package.json` dep reshuffle + regenerated `pnpm-lock.yaml`.
2. Dockerfile restructure + compose `CI_ARG` removal + `.dockerignore` +
   changelog fragment.
