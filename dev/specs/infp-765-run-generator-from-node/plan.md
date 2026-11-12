# Implementation Plan: Run a Generator for a Node from the Node's Page

**Branch**: `run-generator-from-node-infp-765` | **Date**: 2026-10-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/infp-765-run-generator-from-node/spec.md`

## Summary

Add a "Generators" section to the node Actions menu. It lists the generator definitions whose target group contains the node's kind, enables each item only when the node is a direct member of that group, and starts a run for this node only through the existing `CoreGeneratorDefinitionRun` mutation with `nodes: [<node id>]`. The section is visible only to users the backend would allow to run the generator: signed in, and holding `edit_default_branch` on the default branch.

The change is frontend only. Two read requests with existing GraphQL fields decide what to list ([research.md](research.md) R1). The data is read when the menu opens (R2). A pure rule mirrors the backend permission checks (R3). The section shows exactly one toast per outcome (R4).

## Technical Context

**Language/Version**: TypeScript 5.9 and React 19.2 (frontend); Python 3.14 (E2E test only)

**Primary Dependencies**: existing only.

- TanStack Query, gql.tada, urql and `json-to-graphql-query` for requests.
- `@infrahub/ui` `Menu`, `MenuSection` and `MenuItem` (with `isDisabled` and `tooltip`).
- `react-toastify`.

**Storage**: N/A. No stored data or schema changes.

**Testing**:

- Vitest in browser mode (unit and component tests).
- pytest-playwright E2E suite (`tests/e2e/`).

**Target Platform**: Infrahub web UI, served by the Infrahub server.

**Project Type**: Web application. This change touches `frontend/app` and adds tests in `tests/e2e`.

**Performance Goals**: No request on node page load. Opening the Actions menu adds at most three small requests: the definitions list, one aliased count request, and, on the default branch only, the global permission check. The counts select no nodes.

**Constraints**:

- No new mutation, query, schema field, permission or dependency.
- The Actions menu is shared with IP prefix and IP address pages.

**Scale/Scope**:

- One new menu section, five new frontend modules plus a query-keys file.
- Two small changes to shared code: a permission constant, and an optional parameter on `useHasGlobalPermission`.
- One optional parameter on `runGeneratorFromApi`.
- Tests, one docs sentence and one changelog fragment.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | How the design complies |
|---|---|---|
| I. Schema-Driven Integrity | Pass | No schema change. `graphql-cache.d.ts` is regenerated, not edited. |
| II. Branch-Safe by Default | Pass | Every request carries the current branch (and the time-travel date for reads). The default branch is detected with `is_default`, not by name. The run writes only to the current branch. |
| III. Type Safety & Explicit Contracts | Pass | The definitions query is typed by gql.tada. The aliased count response is parsed with a type guard, not `as`. Contracts are in [contracts/](contracts/). |
| IV. Test Discipline | Pass | Unit tests for both rules, a component test for the section, and an E2E test (required for user-facing features). The E2E run test also checks that a run started from the menu creates a generator instance for that node only, which covers the `nodes` argument the feature depends on. |
| V. Query Performance & Efficiency | Pass | Count-only selections fetch no nodes. One request covers all target groups through aliases. No request on page load (R2). |
| VI. Security & Input Boundaries | Pass | Authorization stays at the API. Hiding the section mirrors the server rules and is not an access control; a refused run shows the server's reason. |
| VII. Simplicity & Maintainability | Pass | Reuses the existing mutation, mutation hook, global permission hook and menu section pattern. The shared-code changes are optional parameters that follow existing conventions. |
| Documentation | Pass | `docs/docs/generators/overview.mdx` gains the new path to run a generator. No architecture change, so `dev/knowledge/` is unchanged. |
| Changelog | Pass | One `added` fragment through the `creating-changelog-entries` skill. |

Gates crossed from `AGENTS.md` "Ask First": none. No database or GraphQL schema change, no new dependency, no CI change, no authentication or authorization change.

Post-design re-check: unchanged. All gates pass.

## Project Structure

### Documentation (this feature)

```text
specs/infp-765-run-generator-from-node/
├── spec.md
├── plan.md               # This file
├── research.md           # Phase 0
├── data-model.md         # Phase 1
├── quickstart.md         # Phase 1
├── contracts/
│   ├── graphql-requests.md
│   └── generators-menu-section.md
├── checklists/
│   └── requirements.md
└── tasks.md              # Phase 2 (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
frontend/app/src/entities/generators/
├── api/
│   ├── run-generator-from-api.ts                         # change: optional processErrorMessage
│   ├── get-generator-definitions-for-node-from-api.ts    # new: static typed query (contract 1)
│   └── get-target-group-kind-counts-from-api.ts          # new: aliased count query (contract 2)
├── domain/
│   ├── model/node-generator-definition.ts                # new: NodeGeneratorDefinition
│   ├── rules/select-node-generator-definitions.ts        # new + .test.ts
│   ├── rules/can-run-generators.ts                       # new + .test.ts
│   └── use-cases/get-node-generator-definitions.ts       # new: request 1, then request 2
└── ui/
    ├── queries/generator.query-keys.ts                   # new: under objectQueryKeys
    ├── queries/get-node-generator-definitions.query.ts   # new: useGetNodeGeneratorDefinitions
    ├── queries/run-generator.mutation.ts                 # change: optional config (hook-level callbacks)
    └── node-generators-menu-section.tsx                  # new + .test.tsx

frontend/app/src/entities/permission/
└── ui/queries/has-global-permission.query.ts             # change: optional QueryConfig

frontend/app/src/entities/nodes/object/ui/object-details/
└── object-details-menu.tsx                               # change: render the section before "Manage"

frontend/app/src/shared/api/graphql/generated/
└── graphql-cache.d.ts                                    # regenerated by pnpm codegen:graphql

tests/e2e/objects/
└── test_object_details_generators.py                     # new, shard_branches_repo

docs/docs/generators/overview.mdx                         # change: one sentence
changelog/<fragment>.added.md                             # new
```

**Structure Decision**: The new code lives in the `generators` entity, following the api/domain/ui layers (`dev/knowledge/frontend/entities-structure.md`):

- The `api/` files import only `shared/` and their own entity's `domain/model`.
- The rules are pure.
- The use case composes the two requests.
- The UI reads the query hook.

`ObjectDetailsMenu` only renders the section, passing the node's id, concrete kind (`__typename`) and label.

### Key implementation notes

- **Query keys** extend `objectQueryKeys.all` (pattern: `entities/nodes/object-file/ui/queries/object-file.query-keys.ts`), keyed by node id, node kind, branch and date. Group membership changes, object edits and the header refresh button invalidate them through the existing `objectQueryKeys.all` invalidations.
- **Query hook** follows `entities/nodes/object/ui/queries/get-object.query.ts`: reads `useCurrentBranch()` and `datetimeAtom`, and takes `config?: QueryConfig<...>` so the section passes `enabled: canRunGenerators(...)`.
- **The section component**:
  1. Reads `useAuth()`, `useCurrentBranch()`, then `useHasGlobalPermission(EDIT_DEFAULT_BRANCH, { enabled: isAuthenticated && isDefaultBranch })`.
  2. Computes `canRunGenerators`.
  3. Calls `useGetNodeGeneratorDefinitions` with `enabled` set to that result.
  4. Renders `null` unless data is present and non-empty.
  5. Calls `useRunGeneratorMutation` with `processErrorMessage: () => {}`, disables only the item whose `generatorId` matches the pending mutation's `variables`, and shows the success or error toast from [contracts/generators-menu-section.md](contracts/generators-menu-section.md) from hook-level `onSuccess`/`onError` options, because selecting an item unmounts the section (research.md R4).
- **Toast link** uses `getTaskDetailsUrl(taskId)` (R5).
- **Docs**: `docs/docs/generators/overview.mdx` describes the generator definition page path. Add the node Actions menu path next to it, and run `uv run invoke docs.lint`.

## Complexity Tracking

No constitution violations to justify.

## Phase status

- Phase 0, research: complete ([research.md](research.md)). No open questions.
- Phase 1, design: complete. [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md).
- Agent context update: skipped. `CLAUDE.md` holds no `<!-- SPECKIT START -->` / `<!-- SPECKIT END -->` markers. It only includes `AGENTS.md`, which keeps no per-feature plan reference.
- Phase 2: run `/speckit-tasks`.
