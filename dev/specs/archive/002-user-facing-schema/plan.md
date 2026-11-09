# Implementation Plan: User-Facing Schema Separation

**Branch**: `user-facing-schema-infp-234` | **Date**: 2026-07-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-user-facing-schema/spec.md`; PRD and resolved field mapping at repo root (`PRD-user-facing-schema-separation.md`, `schema-field-classification.md`).

## Summary

Separate Infrahub's user-facing schema from its internal schema by generating, from the single source of truth (`backend/infrahub/core/schema/definitions/internal.py`), three model families instead of one: a **write** model (exactly what `/api/schema/load` accepts), a **read** model (what `/api/schema` returns — a superset that adds visible-but-not-settable fields), and the existing **internal** model (unchanged, backend-only). Each field definition gains a `visibility` classification (`write`/`read`/`internal`, default `internal`) carried in the existing `extra={}` channel. Fields with a known allowed-value set (currently dropped during generation) publish that set into the write/read models. The write and read models are generated into the `python_sdk` submodule so they can validate a schema offline; the backend's API layer consumes those same SDK models, guaranteeing server/client parity. Because `extra="forbid"` is already enforced, a write model that simply omits non-write fields yields the required field-level rejection with minimal new validation code.

## Technical Context

**Language/Version**: Python 3.14 (backend + SDK)

**Primary Dependencies**: Pydantic 2.12 (models), Jinja2 (code generation), FastAPI 0.131 (REST), Invoke 2.2 (task runner). `infrahub-sdk` is a path/editable dependency of the backend (`pyproject.toml:82`, submodule `python_sdk/`).

**Storage**: N/A — no stored-data model change or migration. This is an API-model + code-generation change only.

**Testing**: pytest. Unit (`backend/tests/unit`), component (`backend/tests/component`), functional (`backend/tests/functional/api`), plus SDK-side tests in the submodule.

**Target Platform**: Linux server (backend) + published Python SDK (client, offline-capable).

**Project Type**: Web service backend + shipped client library (SDK). No frontend surface this cycle.

**Performance Goals**: Not a hot path — schema load/read is infrequent and human/agent-driven. Generation is a dev-time step. No specific latency target.

**Constraints**: Generated files must be byte-stable (idempotent regeneration, validated in CI). SDK write/read models must import with zero backend dependency **and be committed, shipped artifacts in the SDK package** (not build-time-only), so a consumer installing only the SDK obtains them. Backward compatibility: previously loadable write-shaped schemas must still load; stored schemas must still read back. Server and SDK ship one contract and must be released compatibly; the submission `version` field is the skew anchor (local validation advisory, server authoritative).

**Scale/Scope**: Four schema families (node, generic, attribute, relationship) × ~20–30 fields each; one generator template; two API endpoints; one SDK schema module.

## Constitution Check

*GATE: evaluated pre-research and re-checked post-design.*

- **I. Schema-Driven Integrity** — ✅ Advances it. Reduces invalid schemas entering the system; no bypass of the schema layer; generated files remain generated (never hand-edited).
- **II. Branch-Safe by Default** — ✅ N/A to data paths. No query or temporal behaviour changes; schema load already runs through branch-aware processing which is untouched.
- **III. Type Safety & Explicit Contracts** — ✅ Directly advances the principle ("REST contracts MUST be defined before implementation; generated types MUST be used by consumers"). The write/read models are the explicit contract, generated and shared by server and SDK.
- **IV. Test Discipline** — ✅ Unit (generator: idempotency, per-model membership, enum propagation), functional (API load rejection + read serialization), SDK offline validation, and server/SDK parity contract test. Frontend E2E is **N/A** (no user-facing UI this cycle) — justified below.
- **V. Query Performance & Efficiency** — ✅ N/A. No new queries.
- **VI. Security & Input Boundaries** — ✅ Advances it. Hard rejection at the API boundary; input validated by generated models; no injection surface introduced.
- **VII. Simplicity & Maintainability** — ✅ Single source of truth → three generated outputs, not multiplied: the generated models become the sole definition of the write boundary, consumed by both the server and the SDK. Retiring the SDK's remaining hand-written schema models is the tracked follow-up that realises the net reduction of parallel definitions; see [the follow-ups](./opsmill-implement-followups.md). The added generation variants are justified below.

**Gate result: PASS.** No unjustified violations. See Complexity Tracking for the two justified additions.

### Frontend E2E justification (Principle IV)

The constitution requires frontend E2E for user-facing features. This feature has **no frontend surface** this cycle (the `schema-visualizer` consumer is explicitly out of scope). The "users" are API/SDK clients and agents. Coverage is therefore backend functional + SDK offline + contract-parity tests. If/when the visualizer consumes the new models, E2E is added then.

## Project Structure

### Documentation (this feature)

```text
specs/002-user-facing-schema/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── schema-models.md      # write/read/internal model shapes + visibility rules
│   └── api-and-sdk.md        # load rejection, read serialization, SDK offline validation
├── spec.md
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
backend/
├── infrahub/core/schema/
│   ├── definitions/internal.py        # SOURCE OF TRUTH — add `visibility` to ExtraField + set per field
│   ├── generated/                     # internal models (unchanged location; regenerated)
│   └── __init__.py, *_schema.py       # rich internal wrapper models (unchanged shape)
├── infrahub/api/schema.py             # load (POST) + read (GET) — consume SDK write/read models
├── infrahub/types.py, core/constants  # ATTRIBUTE_KIND_LABELS, RelationshipKind, etc. (enum sources)
├── templates/
│   └── generate_schema.j2 (+ variant/param + enum rendering)  # generator template(s)
└── tasks/backend.py :: _generate_schemas   # emit write/read families into python_sdk

python_sdk/                            # git submodule (must be checked out for this work)
└── infrahub_sdk/schema/               # REPLACE hand-written schema models with generated write/read
                                       #   + offline validation entry point

tests/
├── backend/tests/unit/…               # generator unit tests
├── backend/tests/functional/api/test_load_schema.py   # load rejection (extend)
├── backend/tests/component/api/test_40_schema.py      # read serialization (extend)
├── backend/tests/component/core/test_schema.py        # model validation (extend)
└── python_sdk/…                       # SDK offline-validation tests
```

**Structure Decision**: Web-service backend + client library. The backend hosts the source-of-truth definitions and the generator; the SDK hosts the generated external (write/read) models; the internal models stay in the backend. This mirrors the existing `protocols.py` generation that already writes into `python_sdk/infrahub_sdk/protocols.py`.

## Complexity Tracking

| Addition | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|-------------------------------------|
| Generating three model families instead of one | The explicit user-facing contract (Principle III) and rejection of non-settable fields require distinct write/read shapes | A single model with runtime filtering cannot express "field absent from the write contract" in a JSON-schema an agent reads, and cannot leverage the existing `extra="forbid"` rejection |
| Backend imports SDK-generated write/read models (inverts today's direction) | Guarantees server/client parity with one implementation; enables offline SDK validation (FR-006/7/8) | Two independently-generated copies (one per side) would be identical by construction but reintroduce a drift-review burden and a second contract to keep honest; the explicit decision (PRD) is single shared models |
