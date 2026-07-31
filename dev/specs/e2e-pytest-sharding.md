# Sharding the pytest e2e suite into ~4 CI jobs

Status: IMPLEMENTED — every test file declares its shard with a module-level
`pytestmark = pytest.mark.shard_<name>` (markers registered in
`tests/e2e/pytest.ini`, `--strict-markers`), the partition is guarded by a
`pytest_collection_modifyitems` hook in `tests/e2e/conftest.py` (runs before
`-m` deselection, so every shard job validates the FULL collection), and the
`E2E-testing-pytest-playwright` job is a 4-way matrix selecting with
`-m shard_<name>`. Measurements taken locally on 2026-06-11 (branch
`fac-e2e-pytest-playwright`, suite at 232 tests); CI runners are slower but
the ratios hold.

## Goal

Replace the single `E2E-testing-pytest-playwright` job (main suite + docs
invocation run serially, ~23 min of pytest wall time locally, more in CI) with
~4 parallel matrix jobs of roughly equal wall time.

## Measured cost structure

One pytest invocation (testcontainers session):

| Component | Local time |
|---|---|
| Stack boot (compose up -> ready) | ~90-95s |
| Leaf-slice loads (rbac/locations/org_registry/profiles_groups/ipam_pools/patch_template) | seconds each |
| `data_sites` chain on top of boot | ~30s |
| `data_topology` + `data_scenario_branches` increment | ~25s |
| `demo_edge_repo` import increment | ~7s |
| Total test execution (setup excluded) | ~1,000s |
| tutorial invocation (self-contained: own stack + load) | 225s wall |

Per-job CI overhead on top (checkout + uv sync + playwright install +
`invoke dev.build` + sweeps): ~4-8 min depending on docker layer cache.

## Principle

Group shards by the DEEPEST data slice they need, then balance by measured
duration. A deeper shard can host any shallower file at zero extra load cost,
which is the balancing dial. Do NOT use pytest-split/pytest-shard duration
balancing: it scatters deep-fixture files across all shards so every shard
pays the full load + repo import, and it needs a `.test_durations` artifact.
pytest-xdist inside one job was also rejected: session-scoped testcontainers
fixtures are per-worker (4 workers = 4 full stacks on one runner) and browser
tests degrade under contention.

## Shard assignment (per-file times in seconds, fixture-setup spikes excluded)

### Job 1 `foundation` — leaf slices only (~251s tests + ~100s stack)

Never loads `data_sites`; quietest stack, home for flake-sensitive UI tests.

- role-management/test_account_management.py (11.1)
- role-management/test_object_permissions.py (9.7)
- role-management/test_roles_management.py (17.2)
- profile/test_profile.py (5.4)
- profile/test_account_tokens.py (4.6)
- objects/hierarchy/test_object_hierarchy_crud.py (26.4)
- objects/hierarchy/test_object_hierarchy_tree_list.py (17.9)
- object-template/test_create_object_instance_using_template.py (9.8)
- object-template/test_template_with_ip_pool.py (14.1)
- object-template/test_template_with_number_pool.py (13.5)
- groups/test_groups.py (14.7)
- ipam/test_ip_prefix_create.py (29.7)
- ipam/test_ip_prefix_list_filters.py (2.7)
- ipam/test_sub_ip_prefix_list_filters.py (2.9)
- resource-manager/test_resource_pool.py (8.2)
- objects/list/test_object_list_bulk_delete_all_rows.py (4.3)
- objects/list/test_object_list_bulk_delete_some_rows.py (6.4)
- objects/profiles/test_profiles.py (23.9)
- objects/profiles/test_multi_profiles.py (10.8)
- objects/test_object_details_delete.py (5.6)
- objects/test_object_dropdown_creation.py (15.3)
- menu/test_menu_view.py (2.2)
- webhook/test_webhook.py (4.7)
- schema/test_schema.py (5.3)
- tasks/test_tasks_view.py (0, fixme-skipped)

### Job 2 `sites-a` — data_sites (~123s tests + ~130s stack)

- ipam/test_ip_namespace.py (47.0)
- ipam/test_ipam_tree.py (6.9)
- role-management/test_global_permissions.py (21.9, leaf-tier; hosted here for balance)
- objects/file-upload/test_file_upload.py (19.8, leaf-tier; hosted here for balance)
- objects/list/test_object_list_select_range.py (55.6)
- objects/test_object_relationships.py (21.7)
- objects/test_object_update.py (17.2)
- triggers/test_triggers.py (20.4)
- test_search.py (8.5)

### Job 5 `tutorial` — the tutorial suite (~225s wall, self-contained)

Runs `tests/e2e/tutorial` as a plain path invocation in a dedicated shard job
(no markers; tutorial-1 merges a branch into main, so it always keeps its own
stack).

### Job 3 `sites-b` — data_sites + data_topology (~328s tests + ~150s stack)

Remaining sites-tier files:

- activities/test_global_activities.py (17.4)
- activities/test_object_activities.py (2.9)
- branches/test_merged_branch_permissions.py (17.3, includes its merge fixture)
- form/test_select_2_steps.py (12.1)
- form/test_multi_select.py (10.7)
- groups/test_groups_filter.py (1.3)
- ipam/test_ip_address_create_with_pool.py (8.9)
- ipam/test_ip_address_list.py (4.8)
- ipam/test_ip_prefix_list.py (7.0)
- object-template/test_template_with_profiles.py (14.1)
- objects/convert/test_object_convert.py (6.7)
- objects/hierarchy/test_object_hierarchy_navigation.py (5.9)
- objects/hierarchy/test_relationship_hierarchical_input.py (5.3)
- objects/list/test_object_list_bulk_edit_some_rows.py (6.3)
- objects/list/test_object_list_search.py (1.7)
- objects/profiles/test_profile_on_generic.py (13.6)
- objects/test_object_metadata.py (6.1)
- resource-manager/test_number_pool.py (13.4)
- schema/test_schema_shortcut.py (5.5)
- test_search_parent_prefixes.py (6.5)

Topology-tier files (the reason this shard loads `data_topology`):

- objects/test_object_details.py (34.4)
- objects/test_object_filters.py (14.8)
- objects/test_object_groups.py (17.5)
- objects/test_object_list.py (40.3)
- events/test_events_rules_actions.py (0, fixme-skipped)

### Job 4 `branches-repo` — full dataset + demo_edge_repo (~278s tests + ~160s stack)

Scenario-branch tier:

- activities/test_global_activities_filters.py (53.7)
- branches/test_branches.py (28.3)
- branches/test_branch_selector.py (4.5)
- branches/test_branch_details.py (3.0)
- ipam/test_ip_prefix_create_with_pool.py (7.1)
- test_login.py (6.9)
- data/test_parity_dump.py (env-gated skip in CI)

Repo tier (demo_edge_repo = full dataset + git import; isolating these means a
repo-import failure kills one shard, not the suite):

- test_breadcrumb.py (15.4)
- objects/CoreGraphQLQuery/test_core_graphql_query.py (11.3)
- objects/test_artifact.py (3.3)
- objects/test_artifact_definition.py (1.5)
- repository/test_repository_objects.py (11.6)
- proposed-changes/test_proposed_changes.py (10.6)
- proposed-changes/test_proposed_changes_checks.py (5.8)
- proposed-changes/test_proposed_changes_diff.py (14.5)

Leaf-tier ballast moved here for balance (full load hosts them for free):

- role-management/test_group_management.py (29.0)
- branches/test_merge_branch.py (13.9)

Rebalanced 2026-06-11 against the first sharded CI run (run 27358443140:
foundation 8.6m / sites_a 5.8m / sites_b 10.0m / branches_repo 9.7m /
tutorial 6.0m of pytest-step time): sites_a had ~4m of headroom, so
ip_namespace + ipam_tree moved over from sites_b and the global_permissions +
file_upload leaf ballast moved over from branches_repo. Expected walls ~8.5m
per data shard. Rebalancing dial: move leaf files anywhere, sites files
between sites_a/sites_b, topology files between sites_b/branches_repo —
re-measure with each shard's CI junit before moving.

## Implementation notes

1. Matrix on the existing job: `strategy.matrix.shard: [foundation, sites_a,
   sites_b, branches_repo, tutorial]`; keep `fail-fast: false`. Shard
   membership is a module-level `pytestmark = pytest.mark.shard_<name>` in
   each test file; the run step does `uv run pytest -c tests/e2e/pytest.ini
   tests/e2e --ignore=tests/e2e/tutorial -m shard_${{ matrix.shard }}`, except
   the `tutorial` shard which runs `tests/e2e/tutorial` directly.
2. Same-runner coexistence: compose project names are uuid-suffixed
   (`generate_project_name`), and the CI job has no leftover-stack sweeps
   (removed 2026-06-11), so two shards scheduled on the same persistent
   runner do not interfere with each other's stacks.
3. Completeness guard: a `pytest_collection_modifyitems` hook in
   `tests/e2e/conftest.py` (registered `tryfirst`, so it sees the collection
   before `-m` deselects anything) requires exactly one shard marker on every
   test outside `tutorial/`, so a new file without a marker fails every shard
   job instead of silently never running.
4. Artifacts: name per shard (`E2E-testing-pytest-playwright-${{ matrix.shard }}`),
   upload `test-results/` + `playwright-junit.xml` (+ docs artifacts on sites-a).
5. Image build: each shard runs `invoke dev.build`; warm layer cache on the
   persistent runners makes this ~1-2 min. If cold-cache x4 proves expensive,
   follow up with a build-once job pushing a sha-tagged image to
   registry.opsmill.io (or `docker save` -> artifact) and set
   `INFRAHUB_TESTING_DOCKER_PULL` accordingly.
6. `INFRAHUB_TESTING_RESPONSE_DELAY` applies to all shards as today; it inflates
   test time (not load), so shard balance should be re-checked once under
   delay mode (use each shard's junit from a delay-mode run).
7. Validation at implementation time: run each shard once on a fresh stack
   locally. Files have only ever run in full-session alphabetical order; a
   per-shard run flushes out accidental cross-file ordering reliance.
8. Timing source: per-file durations above come from
   `pytest --junitxml --durations=0` on 2026-06-11; re-measure with the same
   method when rebalancing (sum junit testcase times per file; subtract the
   first-test fixture-load spikes).
