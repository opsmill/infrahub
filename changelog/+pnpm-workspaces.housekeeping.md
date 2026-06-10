Restructured the frontend tooling around a pnpm workspace:

- All frontend packages (`app`, `packages/ui`, and the `schema-visualizer` git submodule) are now members of a single pnpm workspace at `frontend/` with one shared lockfile; local edits to packages are live-symlinked into the app without re-installing.
- Cross-package dependency versions are managed through the pnpm `catalog:`, giving a single source of truth for React, Vite, Tailwind CSS, TypeScript, and other shared dependencies.
- Hardened the pnpm config: install-time build scripts are disallowed (`allowBuilds`), and Playwright versions are pinned via `overrides`.
- Restructured the node stages of `development/Dockerfile` (shared node base, frontend, docs) with BuildKit cache mounts, enabling parallel builds and much better layer-cache reuse; `pnpm install` only re-runs when a manifest changes.
