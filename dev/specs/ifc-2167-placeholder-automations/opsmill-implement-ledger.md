# Implementation ledger: ifc-2167-placeholder-automations

## Chunk: Phase 1: Setup

| Task | Outcome | Reason when not done |
|------|---------|----------------------|
| T001 | ✅ done | |
| T002 | ✅ done | |

Decisions worth flagging: T001 read the named sections of `display-labels-and-hfid.md`, `computed-attributes.md` and `events.md` in full, and the sections of `query-pattern.md`, `database-schema.md` and `testing.md` that apply to later tasks (query lifecycle and naming, parameter binding, return labels, the `Branch` vertex, test tiers, the Prefect test servers and swapping the workflow adapter for a test double). `backend/tests/component/hfid/` did not exist before; the other parent packages already had an `__init__.py`.
Lint and format: `uv run ruff check` and `uv run ruff format --check` on the four new packages passed ("All checks passed!", "4 files already formatted"). The four packages import through `uv run python -c "import ..."` ("imports ok").

No new or modified tests in this chunk.

## Chunk: Phase 2: Foundational (fingerprint store, collector and decision)

| Task | Outcome | Reason when not done |
|------|---------|----------------------|
| T003 | ✅ done | |
| T004 | ✅ done | |
| T005 | ✅ done | |
| T006 | ✅ done | |
| T007 | ✅ done | |
| T008 | ✅ done | |
| T009 | ✅ done | |
| T010 | ✅ done | |

Decisions worth flagging:

- The decision function is `decide_fingerprint_changes` in `core/template_fingerprint/decision.py`. It returns `to_recompute` and `to_record` sorted by kind.
- The read query filters on `family` and returns only `branch`, `kind` and `fingerprint`, as the contract states. The repository builds each `RecordedFingerprint` with the `TemplateFamily` it was called with, so a vertex whose `family` is not a `TemplateFamily` value is never returned. T008 asked for an explicit skip of such a record: after a filter on a `TemplateFamily` value that check cannot trigger, so it was not written.
- The read query orders by `branch, kind`, because `Query.execute` reads a READ query in pages of `query_size_limit` rows.
- `insert_missing` counts the created vertices in Cypher: each entry carries a fresh uuid, and `sum(CASE WHEN f.uuid = r.uuid ...)` counts the vertices that hold it after the `MERGE`. Query statistics were not used, because a counter that is zero may be missing from them. The repository removes duplicate keys from its input so that a key is not counted twice.
- The delete-branch Query class takes `branch_name` rather than `branch`, because `branch` is a parameter of the `Query` base constructor.
- The collector has two functions: `fingerprints_from_schema_branches(family, schema_branches)` computes the fingerprints without reading the registry, and `collect_schema_fingerprints(family)` reads `registry.default_branch`, `registry.get_altered_schema_branches()` and `registry.schema.get_schema_branch()` and calls it. The unit tests replace `registry.branch` and `registry._schema` with `monkeypatch`.
- T009 asked to reuse existing schema fixtures. The tests build `DisplayLabels` and `HFIDs` directly instead, because no existing fixture builds a processed `SchemaBranch` without a database. The comparison with the trigger definitions uses the peer automation of `TestPerson`, which carries the `TestCar` hash and stays after T020 removes the placeholder definitions. The test reads the refreshed kind from the automation name, because `target_kind` is `None` on peer definitions.
- The md5 values in `test_collector.py` are pinned literals: a change of the hashing would make the first schema update after an upgrade recompute every kind.
- To check that the empty-list test can fail, the early return of `delete` was removed and the test was run. It failed with `assert 1 == 0`, then the early return was put back.

Lint and format: `uv run ruff format` (1 file reformatted) and `uv run ruff check --fix` ("All checks passed!") on the new modules and tests. `uv run ty check` on the same paths printed "All checks passed!". `uv run mypy` on the same files printed "Success: no issues found in 10 source files". The full `uv run invoke lint` and `uv run invoke backend.mypy` were not run in this chunk (T040 runs them).

| Test id | Type (unit/integration/e2e) | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|-----------------------------|-------------|----------------------|---------------------|--------------------|
| backend/tests/unit/core/template_fingerprint/test_decision.py (12 tests) | unit | `cd backend && uv run pytest tests/unit/core/template_fingerprint/ tests/component/core/template_fingerprint/ -v` | 2026-11-19T14:49:57Z | macOS, Python 3.14 | `======================= 25 passed, 17 warnings in 17.39s =======================` |
| backend/tests/unit/core/template_fingerprint/test_collector.py (6 tests) | unit | same command | 2026-11-19T14:49:57Z | macOS, Python 3.14 | `======================= 25 passed, 17 warnings in 17.39s =======================` |
| backend/tests/component/core/template_fingerprint/test_repository.py (7 tests) | integration (component, Neo4j) | same command | 2026-11-19T14:49:57Z | Neo4j started by testcontainers through the local Docker daemon | `======================= 25 passed, 17 warnings in 17.39s =======================` |
