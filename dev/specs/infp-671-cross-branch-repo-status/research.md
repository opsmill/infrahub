# Research: Cross-branch Repository Status Query

**Branch**: `cross-branch-repo-status-infp-671` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

## Summary

Every unknown was resolved by reading the codebase. No external research was needed. The one input
that reshaped the plan is the request to put the query in front of the frontend team as early as
possible: the delivery is split so the GraphQL contract ships first with fabricated attribute values,
and the graph read replaces them in a second increment without changing the contract.

Three facts found during research bound the design more than the spec anticipated:

1. The permission checker pipeline cannot see a hand-written root field. `InfrahubGraphQLQueryAnalyzer`
   maps root field names against schema kinds and skips anything else, so `ObjectPermissionChecker`
   requires nothing for this query. It also derives a single `ALLOW_DEFAULT` or `ALLOW_OTHER` decision
   from the branch the request runs against and never asks for `ALLOW_ALL`. FR-012 has to be enforced
   inside the resolver.
2. Branch-local attribute writes land on the branch the node was loaded from
   (`infrahub.core.attribute.BaseAttribute::get_branch_based_on_support_type`), and the initial value
   of a local attribute on a branch-agnostic node lands on the global branch
   (`infrahub.database.validation::_check_attribute_edge_branch`). The standard read filter therefore
   already yields the inheritance the spec pins: a branch sees its own edge, else the default branch's
   edge as of `branched_from`, else the global creation value. The existing component test
   `backend/tests/component/git/test_utils.py::test_get_repositories_commit_per_branch_branches`
   demonstrates exactly this (`branch3` reads the default branch's commit, `branch2` reads its own).
3. `TERMINAL_BRANCH_STATUSES` in `infrahub.core.branch.enums` is exactly `(MERGED, DELETING)`, so the
   branch list's `exclude_terminal=True` implements FR-002's status exclusion with no new code.

---

## Decision 1: Deliver in three increments, contract first

**Decision**: Split the work into three reviewable changes.

- **Increment A, contract stub**: the GraphQL root field, its types and its complete argument surface;
  a resolver that resolves the repository for real (id or name, kind dispatch, not-found), enforces the
  FR-012 permission for real, reads the real in-scope branch rows through the branch list, and fills
  the per-branch attribute payloads from a deterministic fabrication keyed on the branch name.
  `schema/schema.graphql` is regenerated so the frontend's `pnpm codegen` produces the final types.
  The two attribute-value filters (`sync_status__value`, `internal_status__value`) and the
  `own_values_only` flag are accepted and ignored, which the contract document states.
- **Increment B, graph read**: the core primitive (Query class plus reader component) replaces the
  fabrication; attribute filters become real; the query-count and inheritance tests land. The stub
  module is deleted in this change and its deletion is the acceptance criterion.
- **Increment C, periodic sync**: `get_repositories_commit_per_branch` moves onto the primitive, in
  its own reviewed change as the spec's Governance section asks.

**Rationale**: The frontend team can build the Branches card against real branch rows, real paging,
real permission denials and final generated types while the Cypher is still being written. Keeping
the repository lookup, permission check and branch row set real in the stub means those tests are
written once and survive the swap. Only the attribute values are fabricated, which is the part the
frontend renders through existing cells and does not need to be true.

**Alternatives considered**:

- Hand the frontend a patched `schema/schema.graphql` without merging a resolver. Rejected: codegen
  would work but nothing would answer the query in a running stack, so the card could not be exercised
  end to end.
- Ship the stub behind a setting in `ExperimentalFeaturesSettings`. Rejected: it forces every frontend
  developer to flip a flag and adds a setting that is deleted weeks later.

**Release rule**: a release must not be cut while the stub is live. If one becomes unavoidable, remove
the `InfrahubRepositoryBranchStatus` attribute from `infrahub.graphql.schema::InfrahubBaseQuery` on
the release branch; that single line hides the field. The stub resolver logs a warning on every call so
its presence is visible in logs.

---

## Decision 2: One resolver path, paginate in Python after the attribute read

**Decision**: The resolver always performs the same three reads, in this order:

1. Resolve the repository by id or name with `NodeManager.get_one_by_id_or_default_filter` (kind
   `CoreGenericRepository`; the default filter is `name__value`), then dispatch on the concrete kind.
   No repository kind declares a `human_friendly_id`, so there is no HFID path.
2. Read every in-scope branch row in one call to `Branch.get_list` with `exclude_global=True`,
   `exclude_terminal=True`, a `BranchListFilters` carrying the name filter, `partial_match`, the
   status filter and the new `sync_with_git` filter (set to `True` for `CoreRepository`, unset for
   `CoreReadOnlyRepository`), ordered by the `MetadataOrderInput` when one is given. The call is
   unpaged, which requires widening `Branch.get_list`'s `limit` to `int | None`; the base `Query`
   then takes its chunked read path (`query_with_size_limit`).
3. Read the selected attributes for those branch names in one statement through the primitive
   (Decision 3). Apply the attribute-value filters, the default ordering (default branch first, then
   name ascending) when no `order` was given, then `offset` and `limit`, in Python. `count` is the
   length of the filtered list.

**Rationale**: The PRD identified two resolver shapes and noted that once an attribute filter is in
play the attribute read must cover all in-scope branches or the page boundaries and count are wrong.
Using that shape unconditionally gives one code path to test, a query count of three regardless of
branch count (FR-007), and a `count` that never issues a counting statement (FR-011 holds trivially).
At the spec's target scale (several hundred branches, three attributes) the extra rows on an
unfiltered page are a few hundred small records.

**Alternatives considered**:

- Page branches in the database when no attribute filter is present and use `Branch.get_list_count`
  for `count`. Rejected: a second path with its own tests for a gain that only shows at branch counts
  well beyond the spec's target.
- Read the branch rows from `registry.branch` instead of the database. Rejected: the row set must
  match the branches page the user sees, which reads the database, and the registry is refreshed per
  worker so a branch created seconds ago could be missing on one worker and present on another.

**Consequence**: FR-007's "independent of branch count" holds up to `database.query_size_limit`
branches, above which the chunked branch read adds one execution per chunk. Document, do not engineer
around.

---

## Decision 3: The core primitive is a Query class plus a thin reader component

**Decision**:

- `backend/infrahub/core/query/repository.py::RepositoryBranchAttributesQuery`, a `Query` subclass
  (`type = QueryType.READ`, `insert_return = False`, `insert_limit = False`) taking primitives only:
  `repository_ids: list[str]`, `branch_names: list[str]`, `attribute_names: list[str]`, plus the
  default and global branch names and `at`. It yields
  `RepositoryBranchAttributeValue(repository_id, branch_name, attribute_name, attribute_id, value,
  own_value, updated_at)` frozen dataclasses from `get_data()`.
- `backend/infrahub/core/repository_branch_status/reader.py::RepositoryBranchAttributesReader`, a
  component with `db` injected in the constructor and one entry method
  `read(repository_ids, branch_names, attribute_names, at) -> RepositoryBranchAttributes`.
  `RepositoryBranchAttributes` is a frozen lookup keyed by `(repository_id, branch_name,
  attribute_name)` whose `get` returns `None` for a branch that produced no row (the Python-side
  backfill the PRD found in `infrahub.core.query.diff::DiffCountChanges.get_num_changes_by_branch`).

The Cypher joins each requested branch to its `Branch` node for `branched_from`, then elects the
visible `HAS_ATTRIBUTE` and `HAS_VALUE` edges per `(repository, attribute, branch)` with the
per-branch predicate below and the standard `ORDER BY branch_level DESC, from DESC, status ASC LIMIT 1`
election, exactly as `infrahub.database.validation::_check_duplicate_attributes` does:

```cypher
WITH ..., CASE WHEN br.is_isolated THEN br.branched_from ELSE $at END AS default_window
...
(r.branch IN [branch_name, $global_branch]
   AND r.from <= $at AND (r.to IS NULL OR r.to > $at))
OR (branch_name <> $default_branch AND r.branch = $default_branch
   AND r.from <= default_window AND (r.to IS NULL OR r.to > default_window))
```

The comparison operators are copied from `Branch.get_query_filter_path`, not paraphrased: the standard
filter uses a **non-strict** `from <=` with a strict `to >`, emitted as two arms per branch
(`from <= t AND to IS NULL`, and `from <= t AND to > t`). Only the `branch_agnostic` shortcut in the
same method uses a strict `from <`, and that is not the path this primitive mirrors. Reading the
strict operator off that shortcut would drop an edge written at exactly the query time or exactly at a
branch's `branched_from`. A differential test (Decision 9) pins the
primitive to a standard per-branch read so the two cannot drift. `is_isolated` is deprecated and forced
to true on creation, but the model still carries it and the standard filter still honours a `false`
value from an older database; the `CASE` keeps the primitive consistent with that read.

`own_value` is `r_value.branch = branch_name` on the winning `HAS_VALUE` edge; `updated_at` is that
edge's `from`. Timestamps are ISO strings and compare lexicographically, as the validation module
already relies on.

**Rationale**: FR-009 demands a primitive callable without GraphQL with an explicit branch list and
attribute set. Taking `repository_ids` as a list costs nothing in Cypher (`n.uuid IN $repository_ids`)
and lets the periodic sync read every repository's branches in one statement per chunk, which is what
makes FR-010's bound hold across repositories rather than per repository. The reader component exists
because two callers (the resolver and the sync) need the same backfill and the same result shape, and
because `.agents/rules/backend-component-design.md` keeps Cypher in Query classes and mapping in a
component rather than on a model.

**Alternatives considered**:

- Extend `NodeManager` to return per-branch attribute values. Rejected by the PRD: the manager keys
  nodes by uuid and attributes by node and name, so the branch dimension is discarded before it can
  be returned.
- One `Branch.get_query_filter_path` per branch, concatenated with `OR`. Rejected: it grows the
  statement text with the branch count and defeats plan caching; the `UNWIND` plus `Branch` join keeps
  one plan for any list.

---

## Decision 4: Enforce FR-012 inside the resolver

**Decision**: Two checks in the resolver, both built from
`infrahub.core.account::ObjectPermission(namespace="Core", name=<kind name>, action="view",
decision=PermissionDecisionFlag.ALLOW_ALL)`:

1. Before the lookup: `has_permission` on `Core/Repository` or `Core/ReadOnlyRepository`; if neither
   holds, raise `PermissionDeniedError` without touching the database.
2. After the lookup: `raise_for_permission` on the resolved concrete kind.

`PermissionResolver.resolve_object_permission` checks `combined & required == required`, so
`ALLOW_ALL` is satisfied by one `ALLOW_ALL` grant or by separate `ALLOW_DEFAULT` and `ALLOW_OTHER`
grants, and denied by either alone. Super admins bypass via `has_permission`. A context without a
`PermissionManager` (internal callers build one without an account session) is treated as denial rather
than allowed to surface as `InitializationError`.

**Rationale**: See the summary. Precedent for in-resolver checks on hand-written queries:
`infrahub.graphql.queries.event` and `infrahub.graphql.queries.preferences`. The pre-lookup check exists
because grants are per concrete kind, so the kind is needed for the exact check, yet a caller with no
grant on either kind must not learn whether an id resolves. `prepare_graphql_params` loads a
`PermissionManager` whenever an account session is present, including anonymous sessions, so the
anonymous read path reaches the same checks.

---

## Decision 5: Add `sync_with_git` to the branch list filters

**Decision**: `infrahub.core.branch.filters::BranchListFilters` gains `sync_with_git: bool | None =
None`; `infrahub.core.query.branch::BranchNodeGetListQuery._build_raw_filter` emits
`n.sync_with_git = $filter_sync_with_git` when set; `infrahub.graphql.queries.branch::InfrahubBranchQueryList`
gains a `sync_with_git=Boolean()` argument passed through by `infrahub_branch_resolver`.

**Rationale**: FR-002's row-set criterion and the spec's "reused plumbing" consequence. Exposing it on
the existing branch query is the same three lines and gives the frontend the same filter on the
branches page. This is a GraphQL schema change and needs sign-off with the new query.

---

## Decision 6: The periodic sync reads through the primitive in fixed chunks

**Decision**: `infrahub.git.utils::get_repositories_commit_per_branch` becomes: one
`NodeManager.query` on the default branch for the repository nodes (the branch-agnostic fields and the
`repository` object callers keep using), then one `RepositoryBranchAttributesReader.read` per chunk of
`REPOSITORY_BRANCH_READ_CHUNK_SIZE = 100` branch names over all repository ids, with
`attribute_names = ("commit", "internal_status")`. Branch names come from `registry.branch` minus the
global branch. The constant lives in `infrahub.git.constants`.

The `-global-` key disappears from `RepositoryData.branches`: `sync_remote_repositories` reads the
default branch and the staging branch, `gather_trigger_computed_attribute_python` skips the global
branch. The existing test asserting the key is updated.

**Rationale**: FR-010. Query count becomes `1 + ceil(N / 100)` for N branches, for all repositories
together. A plain constant rather than a `GitSettings` field because no operator has a reason to tune
it, and a setting would need the generated Compose env block, the docs and the dev Compose anchor
updated (`dev/guidelines/backend/checklist.md`).

**Alternatives considered**: keep one `NodeManager.query` per branch and only add the GraphQL query.
Rejected by FR-010 and SC-004.

---

## Decision 7: GraphQL shape reuses existing types and follows `InfrahubBranch` naming

**Decision**: Root field `InfrahubRepositoryBranchStatus` returning `InfrahubRepositoryBranchStatusType
{ count: Int!, edges: [InfrahubRepositoryBranchStatusEdge!]! }`, edge `{ node:
InfrahubRepositoryBranchStatus! }`, node with flat branch scalars (`name`, `status` as the existing
`InfrahubBranchStatus` enum, which the SDL names `BranchStatus`, `is_default`, `sync_with_git`, `branched_from`) and attribute payloads typed with the
existing `TextAttribute` (`commit`, `ref`) and `Dropdown` (`sync_status`, `internal_status`) types.
Arguments: `id: String!` (repository uuid or name), `limit: Int = 40`, `offset: Int = 0`,
`name__value: String`, `partial_match: Boolean = false`, `status__value: BranchStatus`,
`order: MetadataOrderInput`, `sync_status__value: String`, `internal_status__value: String`,
`own_values_only: Boolean = false`. Full SDL in `contracts/graphql-repository-branch-status.graphql`.

Attribute payload population: `id` from the attribute node uuid, `value`, `updated_at` from the
winning value edge, and for dropdowns `label`, `color`, `description` looked up from the attribute
schema's `DropdownChoice` list (the same source `infrahub.core.attribute.Dropdown::color` reads).
`is_default`, `is_protected`, `is_from_profile`, `permissions`, `source`, `owner` resolve to null, as the
spec accepts.

**Rationale**: FR-001, FR-003 to FR-006, FR-013, FR-014. `InfrahubTaskBranchStatus` already exists as
a root field so the name pattern is established. Graphene resolves the reused attribute types from
plain dicts, so no new type or mapping is needed for the frontend's `DropdownCell`.

`sync_with_git` is returned as a row field as well as being the read-write kind's row-set criterion.
It reads constant `true` there, but the read-only kind's row set is every branch, so the value varies
and a caller has no other way to get it from this query. It comes off the `Branch` object the row
already holds.

The Python names for the three graphene types carry a `Node` suffix on the row type
(`InfrahubRepositoryBranchStatusNode`) with `Meta.name` fixing the SDL name, because the unsuffixed
name is also the `Field` symbol registered on `InfrahubBaseQuery`. Two different objects under one
name in one feature is a trap for the next reader, and costs one line to avoid.

---

## Decision 8: Fabricated values in the stub are deterministic and recognisable in code, not in output

**Decision**: `backend/infrahub/graphql/queries/repository_branch_status/stub.py::fabricate_attribute_values`
derives every value from the branch name: `commit` is the SHA-1 hex digest of the name, `sync_status`
cycles through the four schema choices by name hash, `internal_status` is `active` on the default
branch and `inactive` elsewhere, `ref` is `main`, `own_value` is true on the default branch and on
odd hashes, `updated_at` is a fixed timestamp. Labels and colours come from the real schema choices so
the frontend cell renders exactly what it will render later.

**Rationale**: The frontend needs stable values across reloads to build and screenshot against, and
needs every dropdown value to appear so each colour is exercised. Marking the output itself (for
example a `FAKE-` prefix) would break the `Dropdown` contract the card depends on; the markers are the
module name, its docstring, one warning logged when the module is imported into the schema (a warning
per call would flood the log under a refetching card; per-call logging is `debug`), and a "(preview:
attribute values are placeholders, not yet read from the graph)" note in the root field's SDL
description while the stub is live. That description is API-facing, so it names neither the ticket nor
the delivery increment: both are meaningless to a schema consumer, and `.agents/rules/code-doc-style.md`
keeps spec vocabulary out of anything a reader encounters without the spec. Every developer stack built
from `develop` shows these values during the stub window, so the window is announced to the team and
the stub's removal is tracked as its own Jira subtask under INFP-671.

---

## Decision 9: Test placement

- Core primitive: `backend/tests/component/core/query/test_repository_branch_attributes.py`, using
  `tests.helpers.db_query_counter::CountingInfrahubDatabase` for the 5-branch versus 200-branch
  equality (FR-007) and `rows_for` to show rows grow while executions do not. A differential test
  compares the primitive's `(value, updated_at)` for every branch against a standard
  `NodeManager.get_one(branch=...)` read, with one legacy `is_isolated=false` branch in the fixture.
- Shared fixture: the 5-branch and 200-branch sets are one module-scoped fixture built directly with
  `Branch(...).save()` (the `create_branch` flow is seconds per run at 200) and imported by the
  primitive, resolver and sync test modules.
- Resolver: `backend/tests/component/graphql/queries/test_repository_branch_status.py` following
  `test_branch.py` (`TestInfrahubApp`, `prepare_graphql_params`, `tests.helpers.graphql::graphql`),
  covering membership per kind, inheritance and rebase, filters and count, ordering, paging, `ref`
  dispatch, permission matrix (FR-012) including anonymous with and without a role grant and a caller
  with no grant on either kind denied before lookup, zero bus sends via
  `TestHelper.get_message_bus_recorder`, and the field-selection assertion for FR-008 by capturing the
  attribute names the reader receives.
- Pure paging, filtering and default ordering helpers: `backend/tests/unit/graphql/queries/test_repository_branch_status.py`.
- Sync: extend `backend/tests/component/git/test_utils.py` with the FR-010 bound and an assertion that
  `RepositoryData.repository` carries default-branch values (the old loop left whichever branch it
  visited last); add a computed-attribute gather test resolving `branches[branch.name]` for every
  non-global branch.
- Benchmark: `backend/tests/query_benchmark/test_repository_branch_attributes.py` for the primitive.
  The slice exists to change a query-cost profile, and `EXPLAIN` at increment B is a one-off; the
  constitution's Performance Standards name this directory as where the regression guard lives.
- Integration Docker: increment C changes what the computed-attribute trigger gather reads, and
  Principle IV requires a distributed-stack test for changes on that path. Extend
  `backend/tests/integration_docker/test_computed_attributes.py` rather than add a module.
- FR-008's assertion needs no patching. The resolver is a callable class taking the attribute-source
  factory as a required constructor parameter, so the test constructs it with a recording fake. A
  module-level factory reached for from inside a function would leave monkeypatching as the only seam,
  which `.agents/rules/testing-python.md` rules out.
- E2E: the Branches card is built by the frontend team against this contract; the pytest-playwright
  test for the card lands with the card, not with this backend slice. It is a deferral against a MUST,
  so it is only acceptable while tracked: the subtask carrying it is opened in the wrap-up phase.
  `tests/e2e/repository/` already exists and is the likelier home for a repository-page card than
  `tests/e2e/branches/`; the frontend team decides at handoff.

---

## Decision 10: Documentation and changelog

- Increment A: `changelog/+branch-list-sync-with-git-filter.added.md` for the `sync_with_git` argument
  on `InfrahubBranch`, which is a user-visible GraphQL change and ships in this increment. No fragment
  for the query itself: while its values are fabricated it is a preview surface, not a feature.
- Increment B: `changelog/+repository-branch-status-query.added.md`; a short section in
  `docs/docs/git-integration/branch-synchronization.mdx` showing the query; the cross-branch grouped
  read written up in `dev/knowledge/backend/query-pattern.md` and the in-resolver enforcement in
  `dev/knowledge/backend/permissions.md` (both are backend architecture changes, which the constitution
  requires be recorded there, and both are patterns the next hand-written root field will want);
  regenerate `schema/schema.graphql` and run `uv run invoke docs.generate` so reference docs stay valid.
- Increment C: `changelog/+repository-sync-single-read.changed.md`; update
  `dev/knowledge/backend/git-sync.md` with the new read path (one statement per chunk of branches).
- Python SDK exposure of the query is out of scope for this slice and noted for INFP-671 follow-up.

---

## Decision 11: The composition root is `field.py`, not the package `__init__.py`

**Decision**: Both new packages keep an empty `__init__.py`. In
`graphql/queries/repository_branch_status/`, a `field.py` module holds `build_attribute_source`, the
resolver instance and the graphene `Field`, and `graphql/schema.py` imports the field from it directly.
The field is not re-exported through `graphql/queries/__init__.py`. `resolver.py` exposes
`RepositoryBranchStatusResolver`, a callable class whose constructor takes the source factory as a
required parameter.

**Rationale**: three constraints converge on the same shape.

- `dev/knowledge/backend/package-init-files.md` keeps logic and object construction out of
  `__init__.py`, and `graphql/queries/diff/__init__.py` is the precedent: empty, with the field in
  `tree.py` and `schema.py` importing `.queries.diff.tree`. `event.py` and `task.py` are imported the
  same way and are likewise absent from `graphql/queries/__init__.py`, so following the aggregate
  re-export would have meant following the older of two conventions.
- Wiring in `__init__.py` is not merely discouraged here, it does not work: the init would import
  `resolver.py` to pass the resolver to `Field`, while `resolver.py` would import the source factory
  back from the init. Naming a separate composition module removes the cycle.
- `.agents/rules/backend-component-design.md` wants collaborators as required constructor parameters
  and the graph built at the entry point. A resolver reaching for a module-level factory mid-call is
  the shape that rule exists to prevent, and it is also what would force the FR-008 test to patch.

**Alternatives considered**: keep the wiring in `__init__.py` and break the cycle with a function-local
import in `resolver.py`. Rejected: `.agents/rules/python-module-layout.md` allows a function-local
import only to break a genuine circular import, and this cycle is self-inflicted by the file layout
rather than genuine.
