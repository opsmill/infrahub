# Quickstart & Validation Scenarios: Scope display label and HFID recompute

**Date**: 2026-06-19 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Acceptance scenarios mapped to concrete validations. Each maps to a spec requirement and a test level. "DL" = display label, "HFID" = human-friendly ID.

## Developer setup

```bash
uv sync --all-groups
# Unit (fast, no DB)
uv run pytest backend/tests/unit/display_labels/test_scoping.py backend/tests/unit/hfid/test_scoping.py -q
# Component (TestContainers)
uv run pytest backend/tests/component/display_labels/test_scoped_recompute.py backend/tests/component/hfid/test_scoped_recompute.py -q
# Regression guard (the move must not change computed-attribute behavior)
uv run pytest backend/tests/unit/computed_attribute/test_scoping.py backend/tests/component/computed_attribute -q
# Fallback guard (existing full-sweep behavior unchanged)
uv run pytest backend/tests/functional/display_labels/test_display_label_task_optimization.py backend/tests/functional/hfid/test_hfid_task_optimization.py -q
uv run invoke backend.test-unit
```

## Validation scenarios

### A. Unrelated change → zero recompute (P1, FR-001/FR-002, SC-001)
- **Given** kinds with DLs/HFIDs, **when** a schema update changes an attribute no DL/HFID reads,
- **Then** `RecomputeScoper.scope` returns those candidates in `skipped`, and the setup flow submits **no** `TRIGGER_UPDATE_DISPLAY_LABELS` / `TRIGGER_UPDATE_HFID` for them.
- **Test**: component (`WorkflowRecorder` — assert empty submission set), unit (scoper case).

### B. Owner attribute read change → recompute (P1, FR-003)
- **Given** a kind whose DL reads `name`, **when** `name` changes,
- **Then** that kind's DL candidate is `selected` and its update workflow is submitted.
- **Test**: component + unit (both subsystems).

### C. Relationship peer-field change → recompute (P1, FR-003)
- **Given** a kind whose HFID reads `owner__name`, **when** the peer `name` changes,
- **Then** the HFID candidate is `selected`.
- **Test**: component (relationship dataset) + unit.

### D. Definition's own edit → recompute (P1, FR-004)
- **Given** a kind, **when** the schema update changes only its `display_labels` / `human_friendly_id` property,
- **Then** `changed_fields[kind]` contains `"display_labels"` / `"human_friendly_id"`, the deriver's own-field dependency intersects it, and the candidate is `selected`.
- **Test**: unit asserting both the payload token (guards research R1) and selection.

### E. Reads a derived value → always recompute (P1, FR-005)
- **Given** a DL reading `site__display_label`, or an HFID path resolving to a computed attribute, **when** any schema element changes,
- **Then** the deriver returns `depends_on_everything=True` and the candidate is `selected`; `fallback_full_recompute` stays `False`.
- **Test**: unit (`DerivedFieldLookup.is_derived` true) for both the `IMPRECISE_READ_FIELDS` case and the computed-attribute-read case.

### F. No change set → full fallback, unchanged behavior (P2, FR-006, SC-005)
- **Given** a setup invoked with `changed_elements=None` (e.g. branch deletion), **when** it runs,
- **Then** every candidate is `selected`, `fallback_full_recompute=True`, and the existing per-kind hash check + node sweep behave exactly as today.
- **Test**: existing `test_*_task_optimization.py` pass unchanged + a scoper unit case.

### G. DL and HFID scoped independently (FR-007)
- **Given** a kind with both a DL and an HFID with different dependency sets, **when** a change touches only the HFID's dependency,
- **Then** the HFID candidate is `selected` and the DL candidate is `skipped` (and vice versa).
- **Test**: unit + component.

### H. Branch isolation (Constitution II — mandatory)
- **Given** a schema change on branch X, **when** scoping runs,
- **Then** no recompute is submitted for kinds on other branches; changed-element scoping does not broaden branch scope.
- **Test**: component assertion.

### I. End-to-end scoped refresh (Constitution IV — integration_docker)
- **Given** a running stack with nodes across several kinds, **when** a schema update changes one read field,
- **Then** only the affected kinds' stored DL/HFID values change; unaffected kinds' values and recompute activity are untouched.
- **Test**: integration_docker.

### J. Empty / no-op change set (edge)
- **Given** a present-but-empty `ChangedElementSet`, **when** scoping runs,
- **Then** every candidate is `skipped` (no own-field, no read overlap) — zero submissions.
- **Test**: unit.

## Definition of done

- Scenarios A–J covered at the stated levels; all green.
- Regression guard (computed-attribute scoping) and fallback guard (task-optimization) pass unchanged.
- `uv run invoke format lint` and `uv run pytest backend/tests/unit` clean; `mypy` clean on changed files.
- No edits to generated files. No new external dependencies.
- A changelog fragment added under `changelog/` (issue-linked naming per project convention).
