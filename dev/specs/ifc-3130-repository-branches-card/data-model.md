# Data model

The frontend-side model for IFC-3130. Nothing here is stored — every entity is the shape of a read.

**Source of truth**: the frozen backend contract at
`dev/specs/infp-671-cross-branch-repo-status/contracts/graphql-repository-branch-status.graphql`.
Where this document and that one differ, the contract wins.

---

## 1. Repository branch status row

What one repository looks like as seen from one branch. Identified by branch name; the row set
never contains two rows for one branch. Not a stored object — it exists only as a read.

### Wire shape (`InfrahubRepositoryBranchStatus`)

The branch fields reuse `InfrahubBranch`'s value-field types **verbatim, wrappers and nullability
alike**, so one client accessor serves the whole row. The legacy flat `Branch` shape is not the
model here.

| Field | Wire type | Nullable | Meaning |
|---|---|---|---|
| `name` | `RequiredStringValueField!` | `.value` is `String!` | Branch name; joins the repository's per-branch attribute edges |
| `status` | `StatusField!` | `.value` is `BranchStatus!` | Branch status. `MERGED` and `DELETING` are **never returned** |
| `is_default` | `NonRequiredBooleanValueField` | **field and `.value` both nullable** | Whether this is the repository's default branch |
| `sync_with_git` | `NonRequiredBooleanValueField` | **field and `.value` both nullable** | Always true on `CoreRepository`, which selects on it; varies per row on `CoreReadOnlyRepository`, whose row set is every branch |
| `branched_from` | `NonRequiredStringValueField` | nullable | Fork point; inherited rows resolve as of this time |
| `commit` | `TextAttribute` | **nullable**, `.value` nullable | Imported commit as this branch resolves it |
| `sync_status` | `Dropdown` | **nullable** | Import status as this branch resolves it. `Dropdown` carries `value`, `label`, `color`, `description` |
| `internal_status` | `Dropdown` | **nullable** | Present for both kinds |
| `ref` | `TextAttribute` | **null for `CoreRepository`** | `CoreReadOnlyRepository` only — the ref that branch tracks |

Wrapped in:

```graphql
InfrahubRepositoryBranchStatusType {
  count: Int!      # rows after all filters, BEFORE limit/offset  ← the stated total (FR-009)
  edges: [InfrahubRepositoryBranchStatusEdge!]!
}
InfrahubRepositoryBranchStatusEdge {
  node: InfrahubRepositoryBranchStatus!
  node_metadata: InfrahubNodeMetadata!   # ← NOT SELECTED (see below)
}
```

### `node_metadata` is not selected at all

`node_metadata` carries `updated_at`. **Not selecting it is the cheapest possible guarantee for
FR-006** — the card cannot render a "Last import" timestamp, or any substitute for one, from data it
never asked for. This is a structural guarantee, not a rendering choice.

### Domain shape (after the mapper)

The row carries only what a column or the row key needs — the wire shape above is the contract's,
not this card's. A field with no column has no place here; adding one is what FR-006 has to be
argued about later.

```text
RepositoryBranchStatusRow
  __typename    string            ← required by NodeCore, which DataTable's generic constrains to
  id            string            ← SYNTHESISED from name.value (see below)
  name          string            ← name.value (RequiredStringValueField, always present)
  isDefault     boolean           ← is_default?.value ?? false     — the default-branch marker
  commit        string | null     ← commit?.value ?? null
  syncStatus    DropdownValue | null   ← sync_status, guarded (see below)
  ref           string | null     ← ref?.value ?? null  (always null on CoreRepository)

RepositoryBranchStatusPage
  rows   RepositoryBranchStatusRow[]
  count  number      ← the server's count; the ONLY source of the stated total
```

### Row identity

**Synthesise `id` from `name.value` in the mapper.** The contract guarantees one row per branch, so
the branch name is a sound key.

**Do not** relax `DataTable<T extends NodeCore>` or its `getRowId` to accommodate a row without an
`id` — that touches every table in the app, and it is explicitly on the "deliberately not doing"
list.

### Mapper guards (risk 4 — expected to bite during the preview window)

Every one of these is guarded **in the mapper**, never at the call site:

| Guard | Why |
|---|---|
| `is_default?.value ?? false` | `NonRequiredBooleanValueField` — the field itself may be null, not just its value |
| `sync_status` → `null` when the `Dropdown` or its `value` is absent | `sync_status` is a **nullable** `Dropdown`, but `DropdownCell` **requires non-null**. The cell renders nothing for `null` rather than crashing |
| `commit?.value ?? null` | `TextAttribute` is nullable and so is its `value` |
| `ref?.value ?? null` | always null on `CoreRepository`; the column is not rendered at all for that kind |

### Ordering

**The server's**: default branch first, then branch name ascending. This feature **does not impose
an order and does not expose an order control** — the `order` argument is left at its default.

---

## 2. Branch-support declaration

A per-**field** property of the schema stating whether a value is the same on every branch or varies
by branch. Already delivered to the client and already displayed in the schema viewer; **this feature
is the first to make presentation depend on it**.

```text
partitionFieldsByBranchSupport(schema: ModelSchema)
  → { repositoryWide: { attributes, relationships }, branchScoped: { attributes, relationships } }
```

### The three-value mapping

`BranchSupportType` is **`"aware" | "agnostic" | "local"`** (`types.generated.ts`), not a boolean.
The rule is:

```text
branchScoped  ⇔  (field.branch ?? node.branch) ∈ { "aware", "local" }
repositoryWide ⇔ (field.branch ?? node.branch) === "agnostic"
```

**`local` counts as branch-scoped.** Both `aware` and `local` vary per branch; they differ only in
merge behaviour, which is irrelevant to presentation.

Against the real schema
(`backend/infrahub/core/schema/definitions/core/repository.py::core_repository`,
`::core_read_only_repository`, `::core_generic_repository`):

| Field | Kind | `branch` |
|---|---|---|
| `commit` | `CoreRepository` | **LOCAL** |
| `commit` | `CoreGenericRepository` | **LOCAL** |
| `sync_status` | `CoreGenericRepository` | **LOCAL** |
| `internal_status` | `CoreGenericRepository` | **LOCAL** |
| `ref` | `CoreReadOnlyRepository` | AWARE |
| `commit` | `CoreReadOnlyRepository` | AWARE |
| *node level* | all three | AGNOSTIC |

A rule of `branch === "aware" ? branchScoped : repositoryWide` therefore puts **`commit` and
`sync_status` in the repository-wide card on the read-write kind** — the two values this feature
exists to disambiguate — making SC-004 false while read-only tests still pass.

**`internal_status` lands in the branch-scoped card**, because it is declared LOCAL. The design
canvas groups `Internal status` under `Repository`, i.e. repository-wide. **The schema wins** —
FR-019 derives the division from branch support, not from where a field was drawn.
[design.md](design.md) transcribes the canvas and is left as drawn; the divergence is registered as
D-g in [plan.md](plan.md).

**Required test coverage**: one unit case per enum value, `local` included, plus one case exercising
the node-level fallback. Node-level `branch` is a **required** field on `NodeSchemaRead`,
`GenericSchemaRead`, `ProfileSchemaRead` and `TemplateSchemaRead`, so the fallback is total — there is
no third branch to handle.

### Relationships are partitioned too

`ObjectDataDisplay` renders **attributes *and* relationships**. Handing it two derived `ModelSchema`
objects that each keep the full `relationships` array would render `credential`, `tags`,
`transformations`, `queries`, `checks`, `generators` and `groups_objects` **twice** — once
per card.

`RelationshipSchemaRead` carries `branch?: BranchSupportType | null` just as attributes do, so the
same rule applies unchanged. On the repository kinds today every relationship is AGNOSTIC, so they
all land repository-wide and the branch-scoped derived schema gets `relationships: []`.

**Pinned by test**: each relationship label appears **exactly once** on the page.

**One constraint on filtering `relationships`.** `ObjectDataDisplay` reads `objectSchema.relationships`
**twice**: once through `getRelationshipsVisibleInDataDisplay` for what it renders, and again in an
independent `.find()` that locates an attribute's `<attr>__from_resource_pool` companion. A derived
schema whose `relationships` array is filtered therefore loses the pool badge for any attribute whose
companion landed in the other partition.

This does not bite here — the repository schema declares no resource-pool relationships — but it
constrains any later extension of the two-card split to other kinds. If one is needed, the
branch-scoped schema must retain the pool companions of its own attributes rather than taking a blanket
`relationships: []`.

**Shape**: a **pure function**, unit-testable without rendering. It takes a `ModelSchema` and returns
two field sets; the caller builds two derived `ModelSchema` objects from them (D1) and hands each to
`ObjectDataDisplay` via the local `RepositoryDetailsCard` (see D1's revision).

**Empty-partition rule (FR-022)**: a partition with no attributes **and** no relationships MUST NOT
render as an empty titled box. The card is not rendered at all when both lists are empty.

**Kind gate (FR-020)**: the two-card presentation applies only to the repository kinds, gated by
`isOfKind(GENERIC_REPOSITORY_KIND, schema)` — which already resolves both concrete kinds through
`inherit_from`, so **no kind list is needed**. Every other object kind renders exactly as today.

---

## 3. Page window

The position and size of the slice of rows currently shown.

```text
PageWindow
  page      number   1-based, for display and for the controls
  pageSize  number   fixed at 10; not user-selectable, not carried in the URL
  ⟶ derived for the wire:
  limit     number   = pageSize
  offset    number   = (page - 1) * pageSize
```

**Owned by the URL** so it survives a reload and can be shared (FR-011), and **scoped by a required
`urlKey`** so two tables on one route do not share it. `urlKey` is never defaulted — that is the
whole of the collision guarantee, and it is what keeps this independent of the legacy global
`QSP.PAGINATION`.

**Reset rule (FR-014)**: changing *any* filter resets the window to page 1. Because the filters and
the page live under independent URL keys, this reset is a manual call — so it goes **inside a single
`setFilters` wrapper**, never at each filter's own call site (risk 5).

**Counting rule (FR-009, FR-010a)**: the stated total is always `count` from the server — the number
of rows after all filters and **before** limit/offset. It is never the number of rows received.
Rows are **replaced** page by page, never accumulated.

> **Do not pass `count` to `DataTable`.** It renders its own "N counts" footer whenever
> `count !== undefined`, which would collide with FR-010a's window statement. The window statement
> has exactly one source.

---

## 4. Filter set

```text
RepositoryBranchFilters
  nameFragment  string | null    ⟶ name__value + partial_match: true
  status        BranchStatus | null  ⟶ status__value
```

**Wire values are the schema's own (FR-013).** Two traps, both real:

- The branch status enum is **`BranchStatus`** on the wire even though the backend Python symbol is
  `InfrahubBranchStatus`.
- `sync_status` values are **hyphenated** (`in-sync`, `error-import`) even though their labels are
  title-cased (`In Sync`, `Import Error`) and the backend enum members are underscored.

A re-cased or underscored form MUST NOT be sent.

**Three arguments are never sent** — `sync_status__value`, `internal_status__value`,
`own_values_only`. They are not in the filter type and not in the gql.tada document. See the
[UI contract](contracts/repository-branch-status-ui.md).

**Name filtering is debounced** (`useDebounce`) before it reaches the URL and the request.

---

## 5. Typed error (D4)

```text
RepositoryBranchStatusError extends Error
  code: "PERMISSION_DENIED" | "UNKNOWN"
```

Thrown by the **use case**, derived from the GraphQL `extensions` payload against the frontend error
catalogue, which already declares `ERROR_CODES.PERMISSION_DENIED` with a typed `PermissionDeniedData`.

**Reuse the existing parsers.** `hasCatalogueCode` (`shared/api/graphql/error-handling.ts`) already
does this parsing, calling `parseCatalogueError` from `shared/api/errors/` — the use case composes it
rather than re-reading `extensions` by hand.

Verified against the merged backend: the resolver raises `PermissionDeniedError`, a
`ForwardableError` with HTTP 403.

**Why a typed error is necessary**: without it the distinction dies at `graphqlClient.query`, which
rethrows as a bare `Error` with the detail only on `.cause`. The card cannot then tell a denial from
a network failure — and FR-023 requires exactly that distinction, because a denial rendered as
"empty" would tell the user the repository has no branches (SC-007).

Two independently testable levels result: a **use-case unit test** over the raw `extensions` payload,
and a **card test** over the two `code` values.

---

## Entity relationships

```text
Repository (CoreRepository | CoreReadOnlyRepository)
   │
   ├── ModelSchema ──▶ partitionFieldsByBranchSupport()      (agnostic | aware+local)
   │                      ├─▶ repositoryWide  ──▶ derived ModelSchema ──▶ RepositoryDetailsCard ("Details")
   │                      └─▶ branchScoped    ──▶ derived ModelSchema ──▶ RepositoryDetailsCard ("On this branch"
   │                            relationships: []                            + branch-name caption)
   └── InfrahubRepositoryBranchStatus(id, limit, offset, name__value, partial_match, status__value)
          │
          ├── count ──────────────────────────▶ the stated total (title pill + window statement)
          └── edges[].node ──▶ mapper ──▶ RepositoryBranchStatusRow[] ──▶ DataTable ("Branches"
                                                                          | "Infrahub branches")
```

Document order on the page (FR-018a): repository-wide details → branch-scoped details → branches card.
