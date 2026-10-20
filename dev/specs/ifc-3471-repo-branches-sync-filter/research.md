# Research: Filter a repository's branches by sync status

## R1. Backend support

- **Decision**: No backend change.
- **Rationale**: `InfrahubRepositoryBranchStatus` declares `sync_status__value: String` (`backend/infrahub/graphql/queries/repository_branch_status/field.py`). The resolver reads each branch's resolved values, drops rows with `apply_value_filters` (`paging.py`), which compares the resolved `sync_status` exactly, inherited values included, then sets `count` from the filtered rows and pages last. Branch name and status filters are applied first, so all filters combine with AND.
- **Consequence**: The server does not validate the value; an unknown string or `""` returns zero rows. The frontend must send `undefined` when no valid filter is set.

## R2. Source of the filter's values and labels

- **Decision**: The runtime `sync_status` Dropdown attribute of the repository schema the card already receives.
- **Rationale**: Its `choices` carry the labels (Unknown, Import Error, Tracked Ref Missing, In Sync, Syncing), and the Dropdown branch of the dynamic filter input already shows them. The column header uses the same attribute. `sync_status` is defined on `GenericRepository`, so both repository kinds have it.
- **Alternatives**: A static five-value schema in the frontend. Rejected: labels would be copied by hand and the picker would show raw values with a `Text` + `enum` schema.

## R3. Validating the stored value

- **Decision**: Static `FILTERABLE_SYNC_STATUSES` guard in `entities/repository/domain/model/repository.ts`.
- **Rationale**: Mirrors `isFilterableBranchStatus`, keeps the argument mapping independent of the schema, and turns a hand-edited URL value into "no filter" instead of an empty list.
- **Alternatives**: Validate against the schema's choices. Rejected: makes argument mapping depend on the schema. Tradeoff accepted: a sixth backend value would be offered in the picker but not sent until the list is updated, the same limit the Status filter has.

## R4. Showing the label in the Sync Status tag only

- **Decision**: Optional `showChoiceLabels` flag on `ActiveFilterTags`. `formatAttributeFilterValue` receives the attribute schema and, when the flag is set and the kind is Dropdown, returns the matching choice label, or the stored value when no choice matches. Chosen by the user on 2026-10-20.
- **Rationale**: Showing a Dropdown value by its label is a rule of the tag display, not of this card, so it belongs in the shared formatter; showing labels in every table later becomes a change of default. `ActiveFilterTags` has three callers (object tables, the branches list, this card); the other two do not set the flag and keep the stored value. The tag's edit popover renders its own Dropdown input, which already shows labels, so the tag text is the only place to change. The Status filter schema is `Text` with an `enum`, so its tag stays `OPEN` without a special case.
- **Cost**: `formatAttributeFilterValue` changes signature (kind to schema); its call sites and tests change with it. Guard tests prove that a Dropdown tag without the flag and a `Text` + `enum` tag with the flag keep the stored value.
- **Alternatives**:
  - An optional `formatFilterValue` callback supplied by the card. Rejected by the user: the label rule would live in the card instead of the shared formatter.
  - A copied tag component for the card. Rejected: duplicates about 150 lines of selection, edit and remove logic.
- **Choice lookup**: inline `schema.choices?.find(({ name }) => name === value)?.label`, as in two other places; no new shared rule (Principle VII).

## R5. Column header

- **Decision**: Remove `isDisabled`, pass `filterConditions`, no `schema` prop.
- **Rationale**: Without a `schema` prop, `TableColumnHeader` renders the filter-only menu, as for the Status column, so no sort is offered (the query orders by branch metadata only).

## R6. Generated types

- **Decision**: Run `pnpm codegen:graphql` in `frontend/app` and commit `src/shared/api/graphql/generated/graphql-cache.d.ts`.
- **Rationale**: The gql.tada cache is keyed by the document text; PR #10980 regenerated only this file for the same query.

## R7. End-to-end test

- **Decision**: Add `tests/e2e/repository/test_repository_branches_sync_filter.py`, marked `shard_branches_repo`.
- **Rationale**: Constitution Principle IV requires an end-to-end test for user-facing features.
- **Branch setup** (critique E1): On a read-write repository the Branches section lists only branches with Sync with Git turned on (`repository_branch_status/kind_dispatch.py`, `sync_with_git_filter=True`), so the pattern of `test_repository_sync_status.py`, which uses `sync_with_git=False`, would not list the branch. The test creates the branch with `sync_with_git=True`, waits until `demo-edge` is imported on it, sets its `sync_status` to `error-import` through the SDK, and asserts with `expect` polling. Because a synchronization cycle can overwrite a hand-set value, if the value proves unstable the test falls back to values no cycle changes (Import Error yielding the filtered empty state on a shard with no failing branch, then In Sync listing the default branch), and the fixture docstring records why.
