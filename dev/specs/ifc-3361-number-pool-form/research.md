# Research: Number pool create and edit forms

Each decision was checked in the code of this branch. Code is cited by module and symbol.

## R1. How ranges are written

- **Decision**: Create the pool first (generic object create), then one `CoreNumberPoolRangeCreate` per range. On edit, one `CoreNumberPoolRangeDelete`, `CoreNumberPoolRangeUpdate` or `CoreNumberPoolRangeCreate` per changed range.
- **Rationale**: `CoreNumberPoolCreateInput.ranges` is `[RelatedNodeInput]`, which takes only `id`, `hfid`, `kind` and `from_pool`; a range cannot be created nested in the pool mutation. Each range mutation checks overlap against the ranges stored at that moment, under the pool lock (`backend/infrahub/graphql/mutations/resource_manager/number_pools/pool_range.py`, `backend/infrahub/pools/number_pool_range_validation.py`).
- **Alternatives considered**: a backend bulk mutation (out of scope: frontend-only ticket); sending the deprecated `start_range`/`end_range` shorthand (refused on pools with more than one range).

## R2. Order of range writes

- **Decision**: deletes, then updates whose new bounds stay inside the old bounds (including weight-only changes), then other updates, then creates. Stop at the first refusal.
- **Rationale**: frees space before a neighbour grows into it. A swap of two ranges can still be refused; accepted for this version (user decision).
- **Alternatives considered**: delete and re-create every changed range (changes range ids, more calls); temporary bounds (more calls, more failure states).

## R3. Range api functions instead of the generic object hooks

- **Decision**: new api functions for range create, update and delete, called by the use-case `applyNumberPoolRangeChanges`, exposed through one mutation hook that invalidates caches once.
- **Rationale**: `entities/nodes/object/api` create/update/delete functions call `graphqlClient.mutate` without `processErrorMessage`, so `shared/api/graphql/error-handling.ts::handleGraphQLErrors` toasts every refusal; `entities/tasks/api/retry-task-from-api.ts` shows the pattern to suppress it. The generic hooks invalidate object caches after every call. `dev/knowledge/frontend/entities-structure.md` places orchestration in `domain/use-cases`.
- **Alternatives considered**: loop over the generic hooks in the form (double error, N refetches, orchestration in ui).

## R4. Loading the pool for editing

- **Decision**: a dedicated typed query reading `name`, `description`, `node`, `node_attribute`, `allocation_scope`, `pool_type` and `ranges { start end allocation_weight }`.
- **Rationale**: `shared/api/graphql/utils.ts::addRelationshipsToRequest` fetches only `id`, `hfid` and `display_label` of peers; `extraRelationshipNames` cannot request range fields. The same query is refetched after a refused save.
- **Alternatives considered**: extending `extraRelationshipNames` (changes a shared query builder used by six callers of `ObjectEdit`).
- **Open point for implementation**: `ranges` is a paginated relationship; check the default page size and pass an explicit limit if needed.

## R5. Scope candidates

- **Decision**: list only the fields of the selected node kind. A field can be chosen when it is a required attribute of any kind, List and JSON included, that is not the pool's own attribute, or a required relationship of cardinality one, and is not already in the scope. No field can be chosen when the pool's attribute is `unique: true`. Send bare field names on create; read each stored element as a name or as an `{id, name}` object.
- **Rationale**: the [scope spec](../ifc-3185-number-pool-scopes/spec.md) supersedes `dev/specs/ifc-3185-scoped-number-pools/` where they differ. FR-004 allows any attribute kind and refuses optional fields, cardinality-many relationships, paths into related nodes, the pool's own attribute and duplicates; FR-006 refuses a scope on a unique attribute; FR-003 accepts names on creation; FR-002 and FR-018 store and return `{id, name}` objects. The server on this branch still declares `allocation_scope` as a list of strings and does not apply these rules, so the form is the only check for now and reads both shapes.
- **Alternatives considered**: free-text scope entry (no validation); allowing `site__name` paths (refused by IFC-3185).

## R6. Row value shape

- **Decision**: plain strings `{ rangeId?, start, end, weight }`.
- **Rationale**: the `{ source, value }` shape (`dev/guidelines/frontend/object-forms.md`) records where an attribute value came from (profile, pool, template); range rows are peer nodes. `useFieldArray` reserves `id` for its row key, hence `rangeId`.

## R7. State after a refused create (FR-015)

- **Decision**: the form keeps `createdPoolId` in component state and derives `poolId = currentObject?.id ?? createdPoolId`.
- **Rationale**: this is the editing mode, not a copy of a form value, so it does not break the rule against mirroring form state (`dev/guidelines/frontend/page-architecture.md`).

## R8. Empty weight

- **Decision**: send `null`; the field hint says it means lowest priority.
- **Rationale**: `allocation_weight` is optional with no default; a null weight is treated as 0 when allocating (`backend/infrahub/pools/number_pool_space.py`).

## R9. End-to-end coverage

- **Decision**: update `tests/e2e/resource-manager/test_number_pool.py`, `tests/e2e/object-template/test_template_with_number_pool.py` and `tests/e2e/tutorial/guides/test_resource_manager_guide.py` (they fill "Start range *" and "End range *"); add a test that creates a pool with several ranges then edits it, and a test that the schema pool's ranges are read-only (the `service_identifier` pool from `models/base/service.yml`). FR-015 cannot be triggered against a real server because client validation blocks every refusal it could cause, so it is covered by component tests only.
