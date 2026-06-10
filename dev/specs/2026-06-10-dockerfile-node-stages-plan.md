# Dockerfile Node-Stage Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the node side of `development/Dockerfile` into five pinned, parallel, cache-efficient stages and move the vite build toolchain to `devDependencies`.

**Architecture:** A shared `node-base` stage (pinned Node + pinned pnpm) feeds two independent chains: `frontend-deps` → `frontend-build` (pnpm fetch from lockfile, offline install from manifests, then build) and `docs-deps` → `docs` (npm ci, then Docusaurus build). The backend stage imports both artifacts *after* its cached `uv sync` layer. Spec: `dev/specs/2026-06-10-dockerfile-node-stages.md`.

**Tech Stack:** Docker BuildKit (cache mounts, multi-stage), pnpm 10.33.2 (workspace + fetch), npm ci, Docusaurus, uv.

**Branch:** Commit directly on `bab-pnpm-workspaces`. No worktree needed.

**Verification model:** No unit tests exist for Dockerfiles — verification is build-based (TDD does not apply to Tasks 2-6; Task 7 is the verification gate). Task 1 is verified by the app's own build/tests.

---

### Task 1: Move vite build toolchain to devDependencies

**Files:**
- Modify: `frontend/app/package.json:34-136`
- Regenerated: `frontend/pnpm-lock.yaml` (by pnpm, not by hand)

- [ ] **Step 1: Move the 8 packages**

In `frontend/app/package.json`, delete these 8 lines from the `"dependencies"` object:

```json
    "@rolldown/plugin-babel": "^0.2.3",
    "@tailwindcss/vite": "catalog:",
    "@vitejs/plugin-react": "catalog:",
    "babel-plugin-react-compiler": "catalog:",
    "tailwindcss": "catalog:",
    "vite": "catalog:",
    "vite-plugin-monaco-editor-esm": "^2.0.2",
    "vite-plugin-svgr": "^5.2.0",
```

and insert each into the `"devDependencies"` object, keeping both objects alphabetically sorted. The result must have `"devDependencies"` containing (new entries marked):

```json
  "devDependencies": {
    "@betterer/cli": "6.0.0-alpha.1",
    "@betterer/typescript": "6.0.0-alpha.1",
    "@biomejs/biome": "^2.4.16",
    "@graphql-codegen/cli": "^7.1.2",
    "@graphql-codegen/typescript": "^6.0.2",
    "@playwright/test": "1.56.1",
    "@rolldown/plugin-babel": "^0.2.3",
    "@tailwindcss/vite": "catalog:",
    "@types/apollo-upload-client": "18.0.1",
    "@types/dagre": "^0.7.54",
    "@types/node": "catalog:",
    "@types/prismjs": "^1.26.6",
    "@types/react": "catalog:",
    "@types/react-dom": "catalog:",
    "@types/react-syntax-highlighter": "^15.5.13",
    "@types/sha1": "^1.1.5",
    "@vitejs/plugin-react": "catalog:",
    "@vitest/browser-playwright": "^4.1.8",
    "@vitest/coverage-v8": "^4.1.8",
    "babel-plugin-react-compiler": "catalog:",
    "knip": "^6.15.0",
    "openapi-typescript": "^7.13.0",
    "tailwindcss": "catalog:",
    "typescript": "catalog:",
    "ultracite": "^7.8.1",
    "vite": "catalog:",
    "vite-plugin-monaco-editor-esm": "^2.0.2",
    "vite-plugin-svgr": "^5.2.0",
    "vitest": "^4.1.8",
    "vitest-browser-react": "^2.2.0"
  },
```

Do NOT move `tailwindcss-animate`, `react-scan`, or anything else — only the 8 listed packages.

- [ ] **Step 2: Regenerate the lockfile**

Run from the workspace root (NOT frontend/app):

```bash
cd frontend && pnpm install
```

Expected: completes without error; `git status` shows `frontend/pnpm-lock.yaml` modified (the `frontend/app` importer section moves the 8 specifiers from `dependencies` to `devDependencies`; no resolution hashes change).

- [ ] **Step 3: Verify the app still builds**

```bash
cd frontend/app && pnpm build
```

Expected: `vite build` succeeds, `dist/` produced. If it fails with a missing-module error, a moved package is imported by app source — stop and report; do not work around it.

- [ ] **Step 4: Verify unit tests pass**

```bash
cd frontend/app && pnpm test
```

Expected: vitest run passes (same pass/fail set as before the change — run `git stash && pnpm test` to compare if anything fails, then `git stash pop`).

- [ ] **Step 5: Commit**

```bash
git add frontend/app/package.json frontend/pnpm-lock.yaml
git commit -m "refactor(frontend): move vite build toolchain to devDependencies

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Replace the node stages in development/Dockerfile

**Files:**
- Modify: `development/Dockerfile:1-76`

- [ ] **Step 1: Add the NODE_VER arg at the top**

After line 4 (`ARG PYTHON_VER=3.13.11`), add:

```dockerfile
ARG NODE_VER=24.15.0
```

(Global-scope ARG: it must sit before the first `FROM` to be usable in the `node-base` FROM line. `24.15.0` matches the pin already used at `.github/workflows/ci.yml:819`. Do NOT plumb NODE_VER through tasks/ or CI — Dockerfile default only.)

- [ ] **Step 2: Replace lines 34-76 (the `STAGE : Frontend` banner through `RUN npm run build && npm cache clean --force`) with the five new stages**

Delete everything from `# STAGE : Frontend` (line 34) to the end of the docs build (line 76, `RUN npm run build && npm cache clean --force`) and replace with exactly:

```dockerfile
# ****************************************************************
# STAGE : Node base (shared by the frontend and docs builds)
# ****************************************************************
FROM docker.io/node:${NODE_VER}-slim AS node-base

# Keep the pnpm version in sync with "packageManager" in frontend/package.json
RUN npm install -g pnpm@10.33.2 && \
    pnpm config set store-dir /pnpm/store --global

# ****************************************************************
# STAGE : Frontend dependencies
#   pnpm fetch keys on the lockfile alone; the install keys on manifests only.
#   schema-visualizer is a file: dependency, so its full sources must be
#   present at install time (pnpm copies file: deps into the store).
# ****************************************************************
FROM node-base AS frontend-deps

WORKDIR /frontend

COPY frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml /frontend/
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm fetch

COPY frontend/package.json /frontend/
COPY frontend/app/package.json /frontend/app/
COPY frontend/packages/ui/package.json /frontend/packages/ui/
COPY frontend/packages/schema-visualizer/ /frontend/packages/schema-visualizer/
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --offline

# ****************************************************************
# STAGE : Frontend build
# ****************************************************************
FROM frontend-deps AS frontend-build

COPY frontend/packages/ui/ /frontend/packages/ui/
COPY frontend/app/ /frontend/app/
WORKDIR /frontend/app
RUN pnpm build

# ****************************************************************
# STAGE : Documentation dependencies
# ****************************************************************
FROM node-base AS docs-deps

ENV DOCS_IN_APP=1

WORKDIR /docs
COPY docs/package.json docs/package-lock.json /docs/
RUN --mount=type=cache,target=/root/.npm npm ci --omit=dev

# ****************************************************************
# STAGE : Documentation build
#   models/, deploy.tf and k8s/ are raw-loaded by docs .mdx pages at build time
# ****************************************************************
FROM docs-deps AS docs

COPY models/ /models/
COPY development/deploy.tf /development/deploy.tf
COPY development/k8s/ /development/k8s/
COPY docs/ /docs/
RUN npm run build
```

Deliberately removed relative to the old content (do not re-add):
- `ARG CI_ARG` / `ENV CI=$CI_ARG` (inverted semantics; compose side removed in Task 4)
- `corepack enable && corepack prepare pnpm@10 --activate` (deprecated; replaced by pinned global install in `node-base`)
- `mkdir -p /frontend/...` and `mkdir /docs` (COPY creates destinations)
- `pnpm store prune` and `npm cache clean --force` (caches now live in mounts, never in layers)
- `--prod` on the pnpm install (build toolchain is in devDependencies after Task 1)
- `COPY backend/infrahub/config.py /backend/infrahub/` and `COPY python_sdk/docs/docs/python-sdk/examples/ /python_sdk/examples/` (referenced nowhere in docs sources)
- `COPY development/ /development/` (narrowed to `deploy.tf` + `k8s/`, the only paths docs raw-load)

- [ ] **Step 3: Syntax check**

```bash
docker build -f development/Dockerfile --target node-base -q . > /dev/null && echo OK
```

Expected: prints `OK` (also confirms the `node:24.15.0-slim` tag exists). Any `dockerfile parse error` means Step 1/2 was mis-applied.

---

### Task 3: Reorder the backend stage imports

**Files:**
- Modify: `development/Dockerfile` (backend stage — old lines 101-117, now shifted)

- [ ] **Step 1: Move the two import blocks below the dependency install**

In the backend stage, delete this block (currently between the Prefect ENV block and the `# Install Dependencies` comment):

```dockerfile
# --------------------------------------------
# Import Frontend Build
# --------------------------------------------
COPY --from=frontend /frontend/app/dist/ /opt/infrahub/frontend/app/dist

# --------------------------------------------
# Import Documentation Build
# --------------------------------------------
COPY --from=frontend /docs/build/ /opt/infrahub/docs/build
```

and insert this block between `RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project --no-install-workspace` and `COPY . ./`:

```dockerfile
# --------------------------------------------
# Import Frontend & Documentation Builds
#   After the dependency layer so frontend/docs edits don't re-run uv sync
# --------------------------------------------
COPY --from=frontend-build /frontend/app/dist/ /opt/infrahub/frontend/app/dist
COPY --from=docs /docs/build/ /opt/infrahub/docs/build
```

Note both stage names change: `frontend` → `frontend-build` for dist, `frontend` → `docs` for the docs build. No other `--from=frontend` references may remain:

```bash
grep -n -- "--from=frontend " development/Dockerfile
```

Expected: no output.

---

### Task 4: Remove CI_ARG from docker-compose.yml

**Files:**
- Modify: `development/docker-compose.yml:167,224`

- [ ] **Step 1: Delete both build args**

Delete the line `        CI_ARG: ${CI:-0}` in both build blocks (`server` service, line 167, and `task-worker` service, line 224). The `UV_VER` lines stay. Result for both:

```yaml
    build:
      context: ../
      args:
        UV_VER: ${UV_VERSION:-0.9.9}
      dockerfile: development/Dockerfile
      target: backend
```

- [ ] **Step 2: Verify nothing else references CI_ARG**

```bash
grep -rn "CI_ARG" development/ .github/ tasks/
```

Expected: no output.

---

### Task 5: Extend .dockerignore

**Files:**
- Modify: `.dockerignore:18-19`

- [ ] **Step 1: Add the frontend artifact exclusions**

After the existing `frontend/**/playwright-report` line, add:

```text
frontend/**/dist
frontend/**/test-results
frontend/**/coverage
```

(Safe: schema-visualizer's `dist/` is untracked local build output, not checked in — verified via `git ls-files frontend/packages/schema-visualizer/dist` returning nothing.)

---

### Task 6: Changelog fragment

**Files:**
- Create: `changelog/+dockerfile-node-stages.housekeeping.md`

- [ ] **Step 1: Write the fragment**

```markdown
Restructured the node side of `development/Dockerfile` into independent, pinned build stages (shared node base, frontend deps/build, docs deps/build) with BuildKit cache mounts, enabling parallel frontend/docs builds and far better layer-cache reuse. Build toolchain packages (vite and plugins, tailwindcss) moved from `dependencies` to `devDependencies` in `frontend/app/package.json`.
```

---

### Task 7: Build verification

**Files:** none (verification only)

- [ ] **Step 1: Build the frontend chain**

```bash
docker build -f development/Dockerfile --target frontend-build .
```

Expected: succeeds. `pnpm fetch` downloads on first run; `pnpm install --offline` completes without network errors. **Known risk from the spec:** if the install fails resolving the `file:` schema-visualizer dep under `--offline`, remove `--offline` from that single RUN line (keep the cache mount) — that is the approved fallback; note it in the commit message.

- [ ] **Step 2: Build the docs chain**

```bash
docker build -f development/Dockerfile --target docs .
```

Expected: succeeds. If `npm ci` fails with a lockfile-drift error (`npm ci can only install packages when your package.json and package-lock.json are in sync`), regenerate `docs/package-lock.json` with `cd docs && npm install --package-lock-only` and commit it — do NOT revert to `npm install` in the Dockerfile.

- [ ] **Step 3: Full backend build**

```bash
docker build -f development/Dockerfile --build-arg UV_VER=0.9.9 --target backend -t infrahub-dockerfile-test .
```

Expected: succeeds end to end (slow: full uv sync + source copy).

- [ ] **Step 4: Cache-invalidation proof**

BuildKit keys COPY layers on file *content*, so a `touch` proves nothing — make a real edit and revert it after:

```bash
echo "// cache-invalidation-test" >> frontend/app/src/main.tsx
docker build -f development/Dockerfile --build-arg UV_VER=0.9.9 --target backend -t infrahub-dockerfile-test . 2>&1 | tee /tmp/rebuild.log
git checkout -- frontend/app/src/main.tsx
grep -E "CACHED.*(npm ci|npm run build|uv sync|no-install-project)" /tmp/rebuild.log | head
```

Expected: the docs `npm ci` / `npm run build` steps and the first `uv sync` (no-install-project) step all show `CACHED`; only `pnpm build` and the layers after `COPY . ./` re-run. If `uv sync --no-install-project` is NOT cached, Task 3's reorder was mis-applied — fix before committing.

- [ ] **Step 5: Sanity-check the artifacts inside the image**

```bash
docker run --rm --entrypoint sh infrahub-dockerfile-test -c "ls /opt/infrahub/frontend/app/dist/index.html /opt/infrahub/docs/build/index.html && echo ARTIFACTS-OK"
```

Expected: both paths listed, prints `ARTIFACTS-OK`.

- [ ] **Step 6: Commit**

```bash
git add development/Dockerfile development/docker-compose.yml .dockerignore changelog/+dockerfile-node-stages.housekeeping.md
git commit -m "build(docker): split node build into pinned parallel stages

- real docs stage (was fused into the frontend stage): parallel builds,
  independent caches
- pnpm fetch + offline install: lockfile-keyed store, manifest-keyed install
- pin node 24.15.0 (ARG NODE_VER) and pnpm 10.33.2; drop deprecated corepack
- BuildKit cache mounts for the pnpm store and npm cache; drop dead
  store-prune/cache-clean
- npm ci for docs; drop unused docs copies; narrow development/ copy
- import frontend/docs artifacts after the uv dependency layer so
  frontend edits no longer re-run uv sync
- remove inverted CI_ARG plumbing (Dockerfile + compose)
- dockerignore frontend dist/test-results/coverage

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Execution notes

- Task order matters: Task 1 must land before Task 7 (the Dockerfile install runs without `--prod`, which only builds correctly once the toolchain move + lockfile regen are committed). Tasks 2-6 are file edits with no interdependencies and can be done in any order between Task 1 and Task 7.
- Requires Docker with BuildKit (default on Docker ≥ 23) and network access for the first build.
- Do not modify `tasks/container_ops.py`, `tasks/shared.py`, or any `.github/workflows/` file — explicitly out of scope per the spec.
