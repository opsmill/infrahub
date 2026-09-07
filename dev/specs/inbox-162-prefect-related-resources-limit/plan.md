# Implementation Plan: Align Infrahub's event related-resource cap with Prefect's effective limit

**Branch**: `pha/INBOX-162` | **Date**: 2026-09-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `dev/specs/inbox-162-prefect-related-resources-limit/spec.md`

## Summary

`backend/infrahub/events/limits.py` decides how many related resources an Infrahub event may carry
before Prefect would reject it. It currently derives that ceiling from one raw `os.environ` read
with a hardcoded fallback of 500. Prefect's real default is 100, so on any deployment that does not
set the variable — i.e. anything but the shipped image — Infrahub truncates at a budget derived
from 500 and hands Prefect an event it silently discards.

The fix is small and surgical: read the ceiling through **the same accessor Prefect's own validator
uses**, `PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value()`, and fall back to Prefect's documented
default of 100. Nothing else about the module's shape changes — `get_related_resource_budget()`,
`get_submission_chunk_size()` and `MAX_RUN_CONTEXT_RESOURCES` keep their semantics and signatures.

The change carries a required test migration: Prefect snapshots settings from the environment at
import, so the existing tests' `monkeypatch.setenv` will no longer drive the implementation. Every
case moves to `temporary_settings`. See [research.md](./research.md) R4 — this is the part of the
work most likely to be got wrong, because the tests would fail loudly rather than silently, but only
after the implementation lands.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: Prefect 3.7.5 (already a backend dependency — this change reads more of
its public settings surface and adds nothing)

**Storage**: N/A — no persistence involved

**Testing**: pytest 9.0, unit level only (`backend/tests/unit/event/`,
`backend/tests/unit/core/merge/`). Pure logic, no database, no external services.

**Target Platform**: Linux server (Infrahub backend + task worker)

**Project Type**: Web service — backend-only change

**Performance Goals**: N/A. `.value()` is an in-memory settings read on an already-constructed
settings object; it is called once per event-related computation, exactly as the `os.environ` read
was.

**Constraints**: No new dependencies; no DB schema, migration, GraphQL/REST contract, auth, CI, or
generated-file changes; shipped-image behaviour must be bit-for-bit unchanged.

**Scale/Scope**: One module (~50 lines), one test module rewritten to a new override mechanism, two
test modules extended, one changelog fragment.

## Constitution Check

*GATE: evaluated against `dev/constitution.md` v1.0.0 before Phase 0 and re-checked after design.*

| Principle | Applies? | Assessment |
|---|---|---|
| I. Schema-Driven Integrity | No | No schema, no data model, no generated files touched. |
| II. Branch-Safe by Default | No | No database queries, no branch/temporal state. The limit is process-global configuration. |
| III. Type Safety & Explicit Contracts | **Yes** | ✅ All functions keep full type hints. `.value()` returns `int`, so the module's `-> int` contracts hold without casting. No untyped dicts, no new API boundary. |
| IV. Test Discipline | **Yes** | ✅ Unit level is the correct level (pure logic, no external services, runs in seconds). Tests mirror source structure (`backend/tests/unit/event/test_limits.py` ↔ `backend/infrahub/events/limits.py`). No mocking: the tests drive the real Prefect setting through Prefect's own `temporary_settings`, and one test asserts against Prefect's real validator rather than a stand-in. E2E is not applicable — there is no user-facing UI surface. |
| V. Query Performance & Efficiency | No | No queries. |
| VI. Security & Input Boundaries | Marginal | The value is operator configuration, not user input, and Pydantic validates its type before Infrahub sees it. Non-positive values are guarded (research.md R5). |
| VII. Simplicity & Maintainability | **Yes** | ✅ The change *removes* code: a hardcoded constant, an `os` import, and a now-unreachable parse guard. It replaces a re-implementation of Prefect's lookup with the lookup itself. |

**Result**: PASS, no violations, Complexity Tracking not required.

## Design

### D1. Reading the ceiling

Replace the environment read with Prefect's accessor:

```python
from prefect.settings import PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES

PREFECT_DEFAULT_MAX_RELATED_RESOURCES = 100
```

`get_prefect_max_related_resources()` calls `PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value()` and
returns it when positive, otherwise the documented default.

Two properties this buys, both load-bearing for the spec:

- **FR-004 by construction.** `_validate_related_resources` in
  `prefect/events/schemas/events.py:103-111` compares `len(value)` against *this same expression*.
  Infrahub and Prefect therefore cannot disagree — not for either environment-variable alias, not
  for a Prefect profile, not for a config file, and not if Prefect re-plumbs the resolution later.
- **FR-008 for free.** The value is read per call against the live settings context, so
  `temporary_settings` overrides are observed by every caller with no dedicated override hook.

### D2. Which guards to keep — and being honest about what they do

Per [research.md](./research.md) R5, the two current failure branches are no longer symmetric,
because `.value()` returns an already-Pydantic-validated `int`:

- **Parse guard: removed.** A non-numeric value makes Prefect raise `ValidationError` while
  *constructing* its settings — at import, before any Infrahub code runs. Infrahub can neither
  catch it nor fall back, so a `try/except ValueError` would be unreachable code advertising a
  fallback that cannot occur. Deleting it is a deliberate improvement: a typo now fails loudly at
  startup instead of silently selecting a wrong cap, which is the same class of silence this card
  exists to remove. Recorded in the changelog so it is not a surprise.
- **Non-positive guard: kept.** `0` and `-5` are accepted by Prefect and reachable here.

  The docstring must not oversell this guard. With a maximum of `0`, Prefect's validator rejects
  every event carrying any related resource, so returning 100 instead does **not** rescue delivery —
  nothing Infrahub can do would. Its actual job is narrower and worth stating plainly: keep the
  derived budget and chunk size computed from a sane positive ceiling instead of a negative one.

### D3. Test strategy

`monkeypatch.setenv` no longer drives the implementation (research.md R4). The migration is
mechanical but must preserve each existing case's intent and its explanatory comments:

- Replace the module-level `ENV_VAR` constant and every `monkeypatch.setenv(ENV_VAR, ...)` with
  `temporary_settings({PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES: n})`. The dataclass case
  tables keep their shapes, but `configured_max` becomes an `int` rather than a `str` — the string
  form only ever existed because the value came from the environment.
- `test_event_on_the_budget_survives_the_prefect_run_context_append` currently pairs
  `monkeypatch.setenv` *with* `temporary_settings` (it needed the real setting so Prefect's own
  validator agreed). The `setenv` half becomes dead weight; drop it and keep the single mechanism.
- The `BUDGET_CASES` entry for a maximum of 100 already exists and already expects 80. After this
  change that case doubles as the regression test for the new default — worth a comment saying so.

New coverage, placed to match where the existing behaviour lives:

| Requirement | Test | File |
|---|---|---|
| FR-002 / SC-004 (default is 100) | maximum is 100 with nothing configured | `test_limits.py` |
| FR-005 (non-positive → default) | `0` and a negative both yield 100 | `test_limits.py` |
| FR-004 / SC-003 (alias honoured) | overriding via the `PREFECT_EVENTS_…` alias is observed | `test_limits.py` |
| US1 / SC-001 (truncate at 100) | `NodeMutatedEvent.get_related()` truncates to the budget derived from 100 | `test_node_action.py` |
| US2 / SC-002 (unchanged at 500) | the same, tracking 500 | `test_node_action.py` |

The two node-action tests belong beside the existing cap tests
(`test_related_resources_stay_within_prefect_maximum_for_large_relationships`,
`test_truncation_drops_peer_entries_not_node_scoped_entries`) and should follow that file's style.
They must assert against a budget *derived* from the maximum rather than a literal 80 or 450, so
they verify the cap *tracks the setting* — a literal would still pass if the derivation broke.

### D4. Changelog

One `fixed` fragment (FR-009). It is user-visible: events that were silently dropped now arrive.
It should state the affected population (deployments not setting the variable), the symptom
(missing events, automations not firing, nothing in the activity feed), that the shipped image is
unaffected, and the malformed-value behaviour change from D2.

## Project Structure

### Documentation (this feature)

```text
dev/specs/inbox-162-prefect-related-resources-limit/
├── spec.md                 # Phase 1 (specify)
├── research.md             # Phase 0 (this plan's research)
├── plan.md                 # This file
├── quickstart.md           # Verification recipe
├── checklists/
│   └── requirements.md     # Spec quality checklist
└── tasks.md                # Phase 2 (/speckit-tasks)
```

`data-model.md` and `contracts/` are intentionally **not** produced: the change introduces no
entities and no API contract. The three concepts the spec names as entities (maximum, budget, chunk
size) are derived integers, fully described by the module's three existing functions.

### Source Code (repository root)

```text
backend/
├── infrahub/
│   └── events/
│       └── limits.py                          # MODIFIED — the whole production change
└── tests/
    └── unit/
        ├── event/
        │   ├── test_limits.py                 # MODIFIED — migrate to temporary_settings, add cases
        │   ├── test_node_action.py            # MODIFIED — add the two truncation-tracking tests
        │   └── test_group_action.py           # unchanged; must keep passing
        └── core/merge/
            └test_submit_coalesced_recompute.py # unchanged; must keep passing

changelog/
└── +inbox-162-prefect-related-resources.fixed.md   # NEW

development/
└── Dockerfile                                 # UNTOUCHED (keeps =500 deliberately)
```

**Structure Decision**: Backend-only, mirroring the existing layout. `limits.py` is the single
production file; its test module sits at the mirrored path per Constitution IV.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Tests keep `monkeypatch.setenv` and silently stop testing the real thing | Medium — it is the natural, unexamined edit | research.md R4 documents the mechanism; D3 makes the migration an explicit task; the parametrized expectations fail loudly if missed |
| New node-action tests assert literal budgets (80/450) and pass even if the derivation breaks | Medium | D3 requires deriving the expected budget from the maximum |
| Someone "restores" the 500 fallback as a safety measure | Low | FR-003 forbids 500 in the module; a test pins 100; the changelog explains why |
| Reduced budget (450→80) surprises an unconfigured deployment already emitting large events | Low | Those events are being *dropped entirely* today, so any delivery is strictly better; noted in the changelog |
| Non-positive guard read as rescuing delivery at max 0 | Low | D2 and the docstring state plainly that it only keeps the arithmetic sane |

## Verification

See [quickstart.md](./quickstart.md). Gate for done:

- `grep -n '500' backend/infrahub/events/limits.py` → no output
- `uv run pytest backend/tests/unit/event/ backend/tests/unit/core/merge/test_submit_coalesced_recompute.py` → all pass
- `uv run invoke format` / `uv run invoke lint` → clean
- `development/Dockerfile` unmodified in the diff
