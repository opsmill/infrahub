# Research: Owner and source metadata (Community side), storage option B

This file records the design decisions of the plan. Each decision names the code that it builds on, by module and symbol. Paths are relative to `backend/infrahub/` unless they start at the repository root.

Sources of the decisions:

- The spec of this folder, and its sources.
- The option E prototype on the dev VM (spec, "Earlier work on the dev VM"). It is not committed. No prototype of option B exists. The parts of the option E prototype that do not depend on the storage apply to option B.
- The benchmark of 2026-11-09, which holds read and write queries for option B.
- The earlier plans and research of `infp-489-ownership-phase-1` and `infp-489-ownership-phase-2`, which used storage option A. Their decisions on the API, the upgrade and the change check do not depend on the storage.
- The code of this worktree, based on release 1.11.12. The option E prototype is based on a later commit, so graph migration numbers differ.

The Technical Context of the plan has no open "NEEDS CLARIFICATION" item. The open points below are design questions with a proposed answer.

## R-1: Storage structure (option B)

- Decision: store owners as `HAS_OWNER` edges with edge properties, as the spec describes in "Storage constraint: option B".
  - `(:Node)-[:HAS_OWNER]->(owner)` for the own owners of a node. `(:Attribute)-[:HAS_OWNER]->(owner)` for the own owners of an attribute, as today.
  - `(:Node)-[:HAS_OWNER {field}]->(owner)` for an owner of a relationship field of the node.
  - `(:Node)-[:HAS_OWNER {given}]->(owner)` from a profile or an object template, for an owner that it gives to its nodes. With `field` also set, it gives the owner to that field of its nodes. The benchmark used both properties on one edge. The engineering design does not say this.
  - `-[:HAS_OWNER]->(:OwnerMarker)`, with the same `field` and `given` properties, marks the own state of the holder. Only the marker edge means "no owner". The marker edge and owner edges mean those owners. No edge means inherit.
  - The mark for owners copied from an object template is a separate edge from the node vertex to the template, as in the benchmark. It needs the `field` property for a field. The engineering design leaves this point open.
- The marker vertex goes into `core/graph/schema.py`, next to the shared `Boolean` vertices (`GraphBooleanNode`). The edge properties go into the edge model of `HAS_OWNER` in the same file.
- A holder is a vertex with a pair of property values: a node (no property), a relationship field of a node (`field`), the nodes of a profile or template (`given`), one field of those nodes (`given` and `field`), or an attribute vertex.
- Rationale: the request asks for one plan for each of options B and E. The team did not choose on 2026-11-09.
- Alternatives considered:
  - Option E: the sibling plan.
  - Option A (a JSON list in a metadata attribute): ruled out on 2026-11-03.
  - Option D (a field vertex in the link path): ruled out on 2026-11-04.
  - Option C: open in the engineering design, not requested.
- Open: the value of `field`. The design gives the field name, such as `interfaces`. The identifier and the direction of the relationship are an alternative: a rename of the relationship then needs no migration (R-11).

## R-2: Package and components

- Decision: one package `core/ownership/`, with the split that the option E prototype uses:
  - `models.py`: `OwnerState`, `OwnerOrigin`, `HolderKind`, `HolderKey`, `StoredOwnerState`, `StoredNodeOwnership`, `ResolvedOwnership`, `OwnerReference`.
  - `queries.py` and `repository.py`: the Cypher queries and the database access.
  - `resolution.py` and `resolver.py`: the order of sources and the batch read.
  - `writer.py` and `input.py`: writes and input validation.
  - `filter.py`: the owner filter.
- No prototype of option B exists. The models, the resolution, the input parsing and the GraphQL layer of the option E prototype do not depend on the storage, so they can move to option B as they are. The queries, the repository, the writer and the filter must be written for option B. The benchmark of 2026-11-09 holds read queries for option B.
- Rationale: `dev/guidelines/backend/component-design.md` asks for one owner for each concern. The same package layout keeps the two options comparable.
- Alternative considered: a top-level package `backend/infrahub/ownership/`, as in the earlier draft. Rejected: the node layer in `core/` calls it.

## R-3: Resolution of the owners that apply

- Decision: one batch read for each GraphQL request.
  - `core/ownership/repository.py` reads the stored states of the requested nodes, their profiles with priority, and their parents.
  - `core/ownership/resolution.py` applies the order of FR-004 for a node and of FR-005 for a field.
  - The walk to the parents follows the Parent relationship first, then the hierarchy parent (D-3). The option E prototype stops at `MAX_INHERITANCE_DEPTH = 16`. The spec assumes at most 6 levels. Beyond the limit, the prototype returns no inherited owner. No source sets the limit or this result (spec, E-16).
  - `graphql/resolvers/ownership.py` collects the nodes and fields of one request and calls the resolver one time (FR-017).
  - For a relationship, the resolver reads the owners of the field once, and does not read the peers (FR-011).
- Rationale: FR-009 and FR-017 ask for a fixed number of owner queries, and for none when the query does not ask for owners.
- Alternative considered: one read for each node in its field resolver. Rejected: it is an N+1 pattern (constitution V).
- Benchmark of the spec: owners that apply to 50 interfaces in 22.6 ms, to one interface in 3.3 ms.

## R-4: GraphQL output contract

- Decision: the shape of the product meeting of 2026-11-09, in [contracts/graphql-schema.graphql](contracts/graphql-schema.graphql).
  - `ownership` on `node_metadata`, on each attribute and on each relationship field: `state`, `origin`, `origin_node`, `owners`.
  - `target_ownership` and `target_field_ownership(fields:)` on `node_metadata` of profiles and object templates (FR-012).
  - Each owner and the origin node give `id`, `kind`, `display_label`, `hfid` and `is_deleted`.
  - A read of owners needs no view permission on accounts or account groups (D-11).
- Code: `graphql/types/ownership.py::InfrahubOwnership`, `InfrahubMetadataNode`, wired in `graphql/manager.py`.
- The deprecated `owner` field of attributes returns the own owner when the attribute has exactly one, else null (FR-014). `graphql/manager.py` sets the deprecation reason.
- Open: product did not sign off on the names. An API review fixes them before the SDK change (spec, "Questions for engineering").
- The origin value `OBJECT` and the values of `applies_to` (R-15) use "object", as the object permission does. The engineering design names this origin `NODE`, so the API review confirms the name.

## R-5: Write contract

- Decision: no new mutation. The create, update and upsert mutations get new inputs (FR-013):
  - `node_metadata { owners field_owners target_owners target_field_owners sources }`
  - `owners` next to `value` on an attribute input, in `graphql/mutations/attribute.py`
  - An owner is `{id}` or `{hfid, kind}`.
  - A key left out changes nothing. `null` gives inherit. `[]` gives no owner. A list gives own owners (D-5).
- `core/ownership/input.py` validates the input before any write. It refuses the whole mutation for each case of FR-003: owner not found, another kind, unknown kind, neither an ID nor a kind with an HFID, HFID of the wrong length.
- `target_owners` and `target_field_owners` are valid only on profiles and object templates. Infrahub refuses them on other kinds.
- The mutation calls `core/ownership/writer.py` inside its transaction, after the node is saved.
- A change of owners or sources updates `updated_at` and `updated_by` of the node vertex, with the rule of `core/query/node.py::NodeUpdateMetadataQuery` (FR-053, a proposal of the spec). Not checked: whether a mutation that sends only `node_metadata` already updates them.
- A write to the deprecated `owner` field replaces the own owners of the attribute (FR-014).

## R-6: Owner filter

- Decision: two filters on list and count queries, computed in the database before pagination (FR-018 to FR-020):
  - `node_metadata__owners__ids`: a node matches if any owner that applies matches, own or inherited.
  - `node_metadata__owners__isnull`: `true` gives the nodes with no live owner.
  - Code: `core/ownership/filter.py`, called from `core/query/node.py::NodeGetListQuery`. The names are in `core/ownership/constants.py`.
- SC-003 is not met with this filter: about 19.6 seconds for 480,000 interfaces in plain Cypher. The cost through GraphQL was not measured for option B. Most of the cost is the walk to the parents and to the profiles.
- Proposal for the spike, in this order:
  1. Start the query from the owner: find the nodes with the own owner (21.1 ms in the benchmark, because the group vertex also receives the edges of field owners and of profile owners), then go down to the nodes that inherit. The earlier draft with option A met SC-003 for one owner group in this way, and missed it for all 50 groups.
  2. If that does not meet SC-003, build an internal index of the owners that apply, which is not branch data. The session of 2026-10-22 named this fallback.
- If the spike chooses the index, the tasks for its build, its update at each write and its rebuild are added to tasks.md before Phase 3. The index is a new database structure, so it needs approval.
- The spike runs plain Cypher queries on the storage, as the benchmark of 2026-11-09 did. It needs no resolver and no GraphQL layer.
- Edition: this plan puts the filters in Community. If product moves them to Enterprise (Q-23), the filter call in `NodeGetListQuery` and the filter arguments in `graphql/manager.py` need an extension point.

## R-7: Profiles and object templates

- Decision for profiles (D-6): Infrahub reads the owners that a profile gives through the profile, by profile priority. Nothing is copied to the nodes. The owners are `HAS_OWNER` edges from the profile vertex with the `given` property, and with `field` for one field.
- The own owners of the profile are `HAS_OWNER` edges from the same vertex without `given`. So every read of the owners of a profile must filter on the property.
- Decision for object templates (D-7): the create copies the owners that the template gives to the new node and to its fields, and adds the "from template" mark. A write of owners by a user closes the mark.
  - Code: `core/node/create.py`, in the functions that read the template and its subtemplates (`read_template_components`, `read_subtemplates`, `handle_template_relationships`).
  - The create reads the owners of the template and of all subtemplates in a fixed number of queries (FR-027).
- The state of a template copy reads as `INHERIT` with the origin `TEMPLATE`.
- Open (spec): where Infrahub stores the "from template" origin, and how to store the given owners so that the kind migration does not lose them (R-11).
- Each of these cases gets a test (FR-030): a profile changed or removed after nodes use it, and a profile or template changed on a branch and then merged.

## R-8: Node sources

- Decision: `HAS_SOURCE` edges from the node vertex to each source, with branch and time data. No edge means no sources.
  - `core/graph/schema.py::GraphNodeRelationships` declares `HAS_SOURCE` and `HAS_OWNER` for the node vertex as incoming edges only: the node is the source or the owner of an attribute or of a relationship. The declaration must also cover the edges that start at the node (R-11).
  - A node can have the same vertex as owner and as source, for example an account group. Two edges of different types then go from the node vertex to one vertex (R-11).
  - Sources have no "inherit" state, so they need no marker edge and no edge property (D-10).
  - A source is an account, an account group, a repository, a resource pool, a profile or an object template (FR-033).
  - Code: a new module `core/ownership/sources.py` for the read, the write and the filter.
- GraphQL (proposal of this plan): `node_metadata { sources { id kind display_label hfid is_deleted } }`, the input `node_metadata { sources }`, and the filter `node_metadata__sources__ids`.
  - The sources that this plan read give no GraphQL shape for sources. The API review confirms it.
- The diff, the merge and the activity log handle source edges with the owner path of R-9, with the reserved name `node_metadata__sources`.
- The sources of attributes and relationships do not change (FR-035).
- The option E prototype does not hold node sources.

## R-9: Diff, merge, rebase and conflicts

- Finding: the diff and the merge do not read edges from the node vertex today. No prototype of option B exists, so all of this is new work.
- Decision: a separate path for owner edges, with the same module layout as the option E prototype.
  - `core/diff/query/ownership.py`: the diff query, with one pattern for each holder type and an index hint on `owner_branch`. Without them, Neo4j scans all node vertices (357 ms against 14.3 ms in the benchmark).
  - `core/diff/ownership_differ.py`: builds one property for each holder. Its value is the sorted list of owner IDs, and `[]` for no owner. It skips the marker.
  - `core/diff/ownership_fields.py`: holders that are not attributes appear under reserved names: `node_metadata__owners`, `<relationship>__owners`, `node_metadata__target_owners`, `<field>__target_owners`.
  - `core/diff/calculator.py` and `core/diff/query_parser.py` call the differ.
  - `core/diff/query/bulk_merge.py`, `core/diff/merger/merger.py` and `core/diff/merger/exclusion_plan.py`: the merge copies owner edges as a set for each holder and owner. It adds what the branch added and closes what the branch removed.
- The identity of an owner edge in the merge is the start vertex, the end vertex, `field` and `given`. A merge that matches edges by their two vertices only mixes the owners of a node with the owners of its fields.
- The merge keeps the `HAS_OWNER` edges to an owner that the branch deleted (FR-008). If it closes them, the marker edge stays and the node shows "no owner", not "deleted group".
- When a branch deletes a node, the merge closes the outgoing owner edges of the node (E-11).
- A conflict exists when the default branch and another branch change the owner state of the same holder, and the two changes cannot both apply (FR-030). The rule is not decided (spec, "Questions for engineering"). Code: `core/diff/conflicts_extractor.py`.
  - The engineering design expects no conflict when two branches change different owners of one node. This was not tested.
  - The differ builds one property for each holder, with the list of owners as value. So a conflict exists when both sides change the list to different values. The option E prototype has a test for this rule (`test_owner_conflict_resolved_to_base_skips_merge`).
- Display labels (FR-029): `core/diff/enricher/labels.py::DiffLabelsEnricher` already resolves labels for `HAS_OWNER` properties (`PROPERTY_TYPES_WITH_LABELS`). It must resolve each ID of the list, skip the marker, and mark a deleted owner.
- Index: `core/graph/index.py` already has `owner_branch` on `HAS_OWNER(branch)`. Option B needs no new index for the diff (14.3 ms in the benchmark).
- Not measured for option B: the merge, and the cost through GraphQL.
- Each case of FR-030 gets one scenario test with a read on the branch, in the diff and on the default branch after the merge.

## R-10: Upgrade

- Decision: two graph migrations, with the next free numbers when the work starts, and a new `GRAPH_VERSION` in `core/graph/__init__.py`.
  1. Close the `HAS_OWNER` edges from attributes to repositories. Delete nothing, so a query at an earlier time still returns them (FR-036). Owners on links stay.
  2. Hide the attribute owner of the default branch that a branch replaced before the upgrade (FR-037). Option B stores attribute owners in the same way as option E, so it needs the same step as the option E prototype.
- Existing attribute owners have no edge to the marker. Decision: the read treats an owner edge without a marker edge as the own state. New writes always add the marker edge.
  - Rationale: no migration writes one edge for each existing attribute owner on each branch, and a query at an earlier time reads the same state.
  - Alternative considered: the upgrade adds a marker edge for each existing attribute owner. Rejected: it writes to every attribute that has an owner, and a query at a time before the upgrade still needs the read rule.
- From the upgrade, the writer accepts only accounts and account groups as owners, on attributes and on links (D-4).
- Report (FR-038): a command `infrahub db ownership-report` in `cli/db.py`, with its queries in `core/ownership/report.py`. It lists the repository owners, the relationships whose links have owners, and the values with `is_protected` set. It runs before the upgrade, so it must not need the new graph version.
- Deprecations (FR-014, FR-039): `owner` on attributes, `is_protected` and its filter. Their behaviour does not change.

## R-11: Kind change and schema migrations

- Kind change (FR-040): `core/migrations/query/node_duplicate.py::NodeDuplicateQuery`, which `core/migrations/schema/node_kind_update.py::NodeKindUpdateMigrationQuery01` uses, copies the active edges of a node for each edge type of `GraphNodeRelationships`, and gives each new edge a fixed set of properties (`$rel_props_new`).
  - The spec states that the migration keeps only the latest edge between the node and each other vertex. With option B, a node and one of its relationship fields can have the same owner, so two edges go to the same owner vertex and one is lost.
  - The `field` and `given` properties are lost, because the new edge gets the fixed properties only.
  - Decision: the kind migration must change before option B is safe. The copy must keep one edge for each start vertex, end vertex, edge type, `field` and `given`, and must copy both properties.
  - The edge type is part of the key, because a node can have the same account group as owner and as source (`HAS_OWNER` and `HAS_SOURCE`).
  - `GraphNodeRelationships` declares `HAS_OWNER` and `HAS_SOURCE` as incoming edges only, so it must declare both directions.
  - These findings come from a read of the query. No test proves them.
  - A component test changes the kind of a node whose node owners and `interfaces` field owners include the same account group. Both owner states are complete after the change. A second case has the same account group as owner and as source of one node.
- Object conversion: `graphql/mutations/convert_object_type.py::ConvertObjectType` keeps the owners and sources of the node, with the same rule.
- Field rename and removal (FR-041): the `field` property holds the name of the field, so it must follow a rename and a removal. This was not checked in the code.
  - `core/migrations/schema/attribute_name_update.py` and `node_attribute_remove.py`: update or close the `given` edges of profiles and templates that name the attribute.
  - `core/migrations/schema/node_relationship_remove.py`: close the owner edges of the field on each node, and the `given` edges that name it.
  - A relationship rename needs a new migration that updates `field` on every edge, on every branch. The schema has no migration for a relationship rename today.
  - If `field` holds the identifier and the direction (R-1, open), a relationship rename needs no migration.
- Node removal: `core/migrations/schema/node_remove.py` closes the owner edges of the node.

## R-12: Activity log and events

- Decision: a change of owners or sources is part of the node changelog of the mutation, with the old and new owner IDs (FR-031). The event payload keeps the UUIDs.
- The activity log query resolves the display labels when it is read, so a renamed group shows its new name. Code: `graphql/queries/event.py::Events`. The code that formats the changelog of an event was not read.
- A change to the owners of a device sends one event for the device, not for its interfaces (E-4).
- Code: `core/changelog/diff.py` handles `DatabaseEdgeType.HAS_OWNER` as one `owner` property today. It must handle a list.

## R-13: Readers of the latest `HAS_OWNER` edge of an attribute

- Finding: three readers take the latest `HAS_OWNER` edge of an attribute. With several edges, each one returns only one owner, and it can return the marker.
  - The `owner` field of today: `core/attribute.py` and `core/query/attribute.py`.
  - The diff labels: `core/diff/enricher/labels.py`.
  - The changelog: `core/changelog/diff.py`.
- Decision: each reader handles several owners and skips the marker. The `owner` field returns the single own owner, or null.
- Task: search the code for more readers before step 3. Other files read `HAS_OWNER` today, for example `core/query/node.py`, `core/query/relationship.py`, `core/query/subquery.py` and `core/query/resource_manager.py`. With option B, each reader of `HAS_OWNER` from any vertex can meet the marker.
- Open (spec): what the `owner` field returns when its owner node is deleted.

## R-14: Change check

- Decision: an interface that Community owns, with one Community implementation (FR-042, FR-043). Contract in [contracts/change-check.md](contracts/change-check.md).
  - `permissions/change_check/interface.py::ChangeCheck` (abstract class)
  - `permissions/change_check/community.py::ChangeCheckCommunity`: allows everything, reads no owners
  - `permissions/change_check/models.py`: frozen dataclasses for the change set, the refusals and the report
  - `permissions/change_check/collector.py`: builds the change set from the user input and the node changelog
- Wiring: a `build_change_check()` function in `workers/dependencies.py`, with the `_singletons` pattern of `build_ldap_auth_service`. Tests replace the singleton with a test implementation.
  - The repository already has this split for other services: `ldap_auth/service.py::LDAPAuthServiceCommunity`, `proposed_change/approval_revoker.py::ApprovalRevokerCommunity`, `branch/merge_mutation_checker.py::BranchMergeMutationCheckerCommunity`.
  - Not checked: how the Infrahub Enterprise repository replaces a Community class. That repository is not on the dev VM.
- Call sites, all inside the transaction of the mutation, after the write and before the commit:
  - Update, and the update of an upsert: the end of `graphql/mutations/main.py::InfrahubMutationMixin.mutate_update_object`.
  - Create: the end of `core/node/create.py::_do_create_node`, after the template components. `create_node` gets an optional argument, and only the mutations pass it.
  - Relationship add and remove: `graphql/mutations/relationship.py::RelationshipAdd.mutate` and `RelationshipRemove.mutate`, after the write loop.
  - Delete: `graphql/mutations/main.py::InfrahubMutationMixin._delete_obj`, with every node that the cascade removes, before the delete.
  - IP prefix delete: `graphql/mutations/ipam.py::InfrahubIPPrefixMutation.mutate_delete`, which does not use the generic delete.
  - Object conversion: `graphql/mutations/convert_object_type.py::ConvertObjectType.mutate`, as a delete and a create.
- What the check receives (FR-044): the nodes, the action, the fields that the user sent and that changed, both ends of each link with the field on each end, the old and the new parent of a move, and, for a create, the node with the owners that apply after the creation.
- What does not call the check (FR-046): profile values applied to nodes, computed attributes, the components that a template creates, resource pool allocations, and merges. They are not in the user input.
- Refusal (FR-045): the check returns a list of refusals. The mutation raises one error that carries them, the transaction rolls back, and `graphql/error_formatter.py::format_graphql_errors` gives one entry for each refused item. This follows `errors/validation.py::MultiFieldValidationError`. Other mutations of the request still run. An object file load stops at the refused node.
- Rejected: a check in `Node.save`. It would also check the writes of FR-046.
- SC-008: the Community class does no database read, so the cost is the build of the change set.

## R-15: "Applies to", the action for changing owners, the global permission

- Decision (FR-047):
  - A new attribute `applies_to` on `CoreObjectPermission` in `core/schema/definitions/core/permission.py`: Text with an enum and the default `all_objects`.
  - A new enum `PermissionAppliesTo` in `core/constants/__init__.py`: `all_objects`, `owned_objects`, `objects_without_owners`.
  - A new value of `PermissionAction` for changing owners, which `any` does not include. The earlier draft named it `hand_over`.
  - A new value of `GlobalPermissions`. The earlier draft named it `manage_ownership`.
  - The human-friendly ID and the uniqueness constraint of the object permission include `applies_to`. The display label adds it only when it is not `all_objects`, so existing labels do not change.
  - A graph migration sets `all_objects` on every existing object permission, on every branch, and recomputes its stored human-friendly ID.
  - `core/account.py::AccountObjectPermissionQuery` and `AccountRoleObjectPermissionQuery` read `applies_to`. A missing value reads as `all_objects`.
- Decision (FR-048), fail closed:
  - Save time: `core/node/permissions.py::CoreObjectPermission` and `CoreGlobalPermission` call the change check to validate the permission. The Community class refuses `applies_to` other than `all_objects`, the action for changing owners, and the global permission to manage ownership. The message says that the value needs Infrahub Enterprise. This covers GraphQL, the SDK, object files and repository imports.
  - Load time: `permissions/manager.py::PermissionManager` drops every permission with such a value. So `permissions/resolver.py::PermissionResolver` gives the results of today.
- The names are proposals. The API review fixes them.

## R-16: Permission report of each node

- Decision (FR-049, proposal): `node_metadata { permissions { update delete hand_over fields(fields:) { field update } } }` on list and detail queries.
  - One call of the change check for each page gives the values. The same function decides the mutation, so the report and the mutation cannot disagree.
  - In Community, each value is the decision for the kind, as `permissions/resolver.py::PermissionResolver.report_object_permission` gives it today.
- No frontend change uses it in this plan. Infrahub Enterprise and a later frontend spec need it.

## R-17: Account group tree

- Decision (FR-051): a new setting on `config.py::SecuritySettings`, off by default. The earlier draft named it `account_group_tree` (`INFRAHUB_SECURITY_ACCOUNT_GROUP_TREE`).
  - `CoreAccountGroup` inherits the hierarchical `CoreGroup`, so it already has a parent and children.
  - With the setting on, the permission queries of `core/account.py` start from the direct groups of the account and add their ancestors. Membership counts downward only.
  - The same set of groups identifies the user for owners. The change check receives it.
  - The groups load one time for each request, with the permissions.
- Report (FR-052): a command `infrahub db account-group-tree-report` in `cli/db.py`. It lists the users who would gain roles, and the roles. It reads the tree, so it works with the setting off.
- Sign-in does not change: it creates groups with no parent (spec, "Out of scope").

## R-18: Python SDK and object files

- Decision (FR-028): the object file parser of the SDK accepts `node_metadata` and field owners. Contract in [contracts/object-file.md](contracts/object-file.md).
  - The earlier draft changed `python_sdk/infrahub_sdk/spec/object.py` and `python_sdk/infrahub_sdk/node/node.py`. The submodule is not checked out in this worktree, so these paths were not checked.
- The change lands on the SDK repository first, on the branch `infrahub-develop`. The submodule pointer moves after that (`AGENTS.md`, "Submodules").
- The API review comes before the SDK change.
- Follow-up outside this repository: Infrahub Sync needs a setting to send its source through `node_metadata.sources`.

## R-19: Tests and measurements

- Unit tests: the resolution order, the input parsing, the change set collector, the Community change check.
- Component tests: storage, resolver, writer, filter, sources, each merge case of FR-030, each migration, the kind change.
- Functional tests through GraphQL: the scenarios of the user stories. These are the tests of the user-facing API.
- Query benchmarks in `backend/tests/query_benchmark/`: SC-001 to SC-006 and SC-008, on the reference data set.
- Integration Docker test in `backend/tests/integration_docker/`: a kind change and a field rename on nodes with owners. The constitution asks for this level for schema migrations.
- E2E tests in `tests/e2e/ownership/`: one scenario for each of user stories 1 to 6, through the SDK client fixture `infrahub_client` on the full stack. They open no page. User story 7 has none, because its setting needs its own stack.
- Spike, before the first pull request: SC-003 to SC-006, SC-009 and SC-010 with plain Cypher queries. A second measure of SC-009 and SC-010 uses a test implementation of the change check that reads owners.
- Not measured so far for option B: the merge, the kind migration, the cost through GraphQL and concurrent writes.
- The existing permission tests must pass without changes (SC-007).

## R-20: Generated files, docs and changelog

- `schema/schema.graphql`: `uv run invoke schema.generate-graphqlschema`.
- Frontend GraphQL types: `cd frontend/app && pnpm codegen`. This regenerates files and is not a frontend change. CI fails if they are stale.
- Core schema and protocols: `uv run invoke backend.generate`.
- Reference docs: `uv run invoke docs.generate`, for the new setting, the CLI commands and the schema.
- Internal docs: `dev/knowledge/backend/database-schema.md`, `permissions.md`, `mutations.md`.
- User docs in `docs/docs/`: owners, sources, the deprecations, the upgrade report, the group tree setting.
- Changelog fragments for each user-visible change.

## R-21: Concurrent writes and locks

- Requirement: FR-032. Two writes of owners or sources on one item must keep one owner state, which is the complete state of one of the writes. On one branch, the state of the last write stays (a proposal of the spec).
- Option B creates no vertex for a set of owners, so two branches cannot create the same set twice.
- Proposal: a mutation that writes owners or sources takes a lock for the node, with `lock.py::InfrahubMultiLock`.
  - Two writers on one branch run one after the other, so the second one reads the edges of the first one.
  - Value writes take no owner lock.
- Open (spec): what the merge does when two branches leave two active edges between the same two vertices. This spec lists the point for option B, because option B also stores several owner edges on one vertex.
- The marker vertex receives one edge from every holder with an own state. Infrahub already uses shared vertices, for example the two `Boolean` vertices of `IS_PROTECTED`. The benchmark measured writes of 1.4 to 2.5 ms for each call. It did not measure concurrent writes.
- A test runs two first writes of owners on one node at the same time, and merges two branches that each set the first owners of the same field.

## R-22: Open points that the tasks carry

- The label of the marker vertex, the names of the edge properties, and the names of the fields, filters and object file keys (API review).
- The edition of the owner and source filters, and of the detailed refusals (Q-23). The plan assumes Community for the filters.
- Whether one change in the history of a profile is enough for audits (D-6).
- The reference data set and the numbers of the success criteria.
- Whether the `ownership` block gives the profile as origin node for a field whose node takes its owners from a profile (E-15).
- No limit on the number of owners of one item. A reviewer asked about a limit and pagination.
- The rule for conflicts between owner changes (FR-030, R-9).
- The result of two writes of owners on one item at the same time (FR-032, R-21).
- The depth limit of the walk to the parents, and the result beyond it (E-16, R-3).
- Whether a change of owners or sources updates the audit metadata of the node (FR-053, R-5).
