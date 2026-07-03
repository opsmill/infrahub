## Architecture

Feature-Sliced architecture using DDD/Hexagonal principles. Each **context** (entity) keeps its
domain logic, data access, and UI strictly separated, and owns everything specific to that context.

- **app/** — application core (providers, routing, styles)
- **pages/** — route-based page components (thin route wrappers)
- **entities/** — business contexts (features)
- **shared/** — generic, context-free building blocks only

Dependency rule: `app → pages → entities → shared` (unidirectional).

### The mental model

- **Context-specific code lives in its context** (`entities/<context>/`). A context's component,
  hook, type, or function may be imported from anywhere — other contexts and even `shared/`.
- **`shared/` holds only generic, context-free code** — things that belong to *no* context. If a
  file in `shared/` needs to know about a context (a schema kind, an entity's shape, a specific
  component), it is misplaced: move it into that context.
- **The form subsystem (`shared/components/form/`) is the one sanctioned exception**: it lives in
  `shared/` yet composes many contexts (it renders the right form per node kind). Treat it as a
  cross-context framework, not ordinary shared code.
- A few transport files under `shared/api/` legitimately reach two cross-cutting contexts —
  `authentication` (the API clients need the access token) and `nodes/filters` (the GraphQL query
  builder needs the `Filter` type). These are accepted cross-cutting edges, not a general licence.

#### Known exceptions (migration debt)

`shared/` is not yet a clean leaf. Beyond the sanctioned edges above, these files still import
contexts today. The rule stands — do not add new edges like them; migrate these into their contexts:

- `shared/api/graphql/utils.ts`: also imports `ipam/ip-availability` and `schema` domain models
- `shared/api/rest/client.ts`: imports `authentication`'s `ui/queries` refresh-token query, beyond
  the token surface
- Most of `shared/components/inputs/` (`peer`, `enum`, `dropdown`, `pool-select`,
  `relationship-one`/`-many`, `node-kind-select`, `kind-multi-select`): import the `schema` and
  `nodes` contexts
- `shared/components/display/slide-over.tsx`, `shared/components/display/meta-details-tooltips.tsx`,
  `shared/components/table/data-table.tsx`, `shared/components/ui/id.tsx`, and
  `shared/libs/graphiql/use-graphiql-fetcher.ts`

## Entity (context) structure

```text
entities/{context}/
├── api/                # Transport + anti-corruption. FLAT (no subfolders). Owns generated wire
│                       # types and gql/REST calls. Returns domain types.
├── domain/             # Framework-free business core
│   ├── model/          # Vocabulary: types, kind constants, states, inputs, results
│   │                   #   (MAY import generated types, incl. wire DTOs)
│   ├── rules/          # Pure, no-I/O functions (predicates, extraction, shaping)
│   └── use-cases/      # Orchestration: composes model + rules, calls own api/
└── ui/                 # React. Nested subfolders OK (queries/, hooks/, routing/, component groups)
```

Do **not** add an entity-root `types.ts`/`constants.ts`, an entity-root `utils/` folder, or an
entity-root `stores.ts`. Types and vocabulary go in `domain/model`; pure helpers in `domain/rules`;
React helpers/state in `ui/`. Use-cases always live in `domain/use-cases/` (even a single one).

Known exceptions (migration debt): `branches/stores.ts`, `schema/stores/`,
`proposed-changes/stores/`, the stray root component `nodes/getObjectItemDisplayValue.tsx`, and the
flat `domain/` folders in `artifacts`, `user-profile`, and `nodes/object-file`. See
`entities-structure.md` for the full list — do not copy these patterns.

See `entities-structure.md` for the full layer import rules, the data-flow, and worked examples.

## What is generic vs context-specific

- **Generic → `shared/`:** UI primitives with no context knowledge, generic utils (`array`, `date`,
  `file`), the API clients, generic display constants (`MAX_VALUE_LENGTH_DISPLAY`), and query-string
  keys (`shared/config/qsp.ts` — `QSP.*`).
- **Context vocabulary → the context's `domain/model`:** schema kinds (`NODE_OBJECT`,
  `ARTIFACT_OBJECT`, …), states, event-type names, filter names — never `shared/config/constants.ts`.
- **Pagination page size is a UI concern:** the `ui/queries` layer owns the page-size constant and
  passes it to the domain use-case as `limit`; the domain never defaults to a UI page size. (Known
  exception: `BRANCHES_PER_PAGE` currently lives in `entities/branches/api/get-branches-from-api.ts`
  — migration debt, not a precedent.)

## Generated Files (Do Not Edit)

- `src/shared/api/graphql/generated/` — GraphQL types
- `src/shared/api/rest/types.generated.ts` — REST types

Generated types are the backend↔frontend contract and **may be used directly in `domain/`** (see
`entities-structure.md`). Regenerate with `pnpm codegen`.
