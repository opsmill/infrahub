Consolidated the frontend on a single linter and formatter. `frontend/packages/ui` and
`frontend/packages/graph` used `oxlint` + `oxfmt`, which nothing in CI ever ran, while
`frontend/app` used Biome; both packages had therefore been unchecked since they were created.
Biome now owns the whole `frontend/` pnpm workspace from one root config, and CI's `frontend-lint`
job gates the app and the packages in a single step.
