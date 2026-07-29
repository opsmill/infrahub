# Implementation Plan: Bare IP addresses on IPHost attributes

**Branch**: `bare-ip-attribute-infp-551` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/infp-551-bare-ip-attribute/spec.md`

## Summary

Add an `allow_prefix: bool = True` parameter to a new kind-specific `IPHostAttributeParameters`
class. When set to `false`, `IPHost.validate_format` rejects any value carrying a non-host subnet
prefix and `IPHost._normalize_value` stores the address with no mask instead of
`with_prefixlen`. Because both hooks already receive the attribute's schema, and because every
read surface — GraphQL `value`, uniqueness, HFID, display label, the UI's text rendering — reads
the stored value, one change to normalisation carries the whole feature. The derived `prefixlen`
keeps being written to storage, so containment and range queries are untouched. The parameter is
classified `UpdateSupport.NOT_SUPPORTED`, which the existing schema-diff walker already enforces
at the `parameters.allow_prefix` path — that is what makes the change migration-free.

Research (see [research.md](./research.md)) shifted the effort distribution substantially versus the
PRD's module sketch:

- **Backend** is the real work: two new schema types, two parameter-aware methods, one internal-schema
  registration, and regenerated artefacts.
- **Frontend** collapses to **tests only**. There is no IPHost prefix-length control in the codebase to
  suppress (R6), so FR-010 already holds; what is missing is a regression test pinning it.
- **SDK** reuses the `IPAddress` protocol types and `ip_address` mapper that SDK PR #1190 already
  merged (R7). The residue the PRD flagged for cleanup becomes the live code path, so "clean up the
  dead path" and "implement FR-011" are the same edit.

## Technical Context

**Language/Version**: Python 3.14 (backend, SDK), TypeScript 5.9 / React 19.2 (frontend)

**Primary Dependencies**: Pydantic 2.12, FastAPI 0.131.0, graphene (GraphQL), stdlib `ipaddress`.
No new dependencies.

**Storage**: Neo4j 2026.05. **No graph change**: no new value-node label, no new index, no
`GRAPH_VERSION` bump, no data migration. The `AttributeIPHost` label and its
`value`/`is_default`/`binary_address`/`version`/`prefixlen` property shape are unchanged for every
attribute, flagged or not. Only the `value` *string* differs, and only for attributes that opt in.

**Testing**: pytest 9.0 (backend unit + component), Vitest 4.1 (frontend unit), Playwright 1.60 (E2E),
pytest for the SDK.

**Target Platform**: Linux server (backend), browser (frontend), Python library (SDK).

**Project Type**: Web application spanning backend, frontend, and a Python SDK submodule.

**Performance Goals**: No change. The feature adds one attribute-parameter read per value validation
and one per normalisation — both in-memory on an already-loaded schema object. No new queries, no
change to any existing query plan.

**Constraints**:

- No `GRAPH_VERSION` bump and no stored-value rewrite (SC-005).
- Existing `IPHost` behaviour byte-identical (FR-012, SC-006).
- Cross-repo ordering: the SDK commit must be **pushed** before the `python_sdk` submodule pointer
  moves here, and must be **merged** (with the pointer re-pointed to the merged commit) before the
  Infrahub PR merges.
- The internal schema gains a field → core-schema diff → regenerated artefacts must be committed or
  CI fails.

**Scale/Scope**: ~6 backend files, ~2 SDK files, 0 frontend source files (tests only), plus regenerated
artefacts. Roughly 12 new/changed test files.

## Constitution Check

*GATE: evaluated before Phase 0 research and re-evaluated after Phase 1 design.*

| Principle | Verdict | Basis |
|-----------|---------|-------|
| **I. Schema-Driven Integrity** | ✅ Pass | Intent becomes schema-expressible. The declaration is immutable, so no migration can leave data and schema disagreeing. All generated files are regenerated, never hand-edited (see Generated Artefacts). |
| **II. Branch-Safe by Default** | ✅ Pass, with required test | No new queries, so no branch/temporal filters to write. The attribute parameter travels with the schema, which is already branch-aware. Merge behaviour is specified (bare and host-mask forms converge → no conflict) and **must** be tested before completion — task in Phase E. |
| **III. Type Safety & Explicit Contracts** | ⚠️ **Deviation — justified below** | `IPHost.value`'s serialised form becomes conditional on a schema parameter. See Complexity Tracking. |
| **IV. Test Discipline** | ✅ Pass | Unit (validation/normalisation, schema types, SDK coercion), component (DB round trip, HFID, uniqueness, containment, schema-update rejection, profile/template, branch merge), frontend unit regression, Playwright E2E. Test files mirror source structure. Existing schema fixtures reused where they suffice. |
| **V. Query Performance & Efficiency** | ✅ Pass | Zero new or modified queries. `prefixlen` stays populated specifically so existing containment query plans are unchanged (R3). |
| **VI. Security & Input Boundaries** | ✅ Pass | The change *tightens* an input boundary: flagged attributes reject a value class previously accepted. Rejection uses the existing `ValidationError`, which names the attribute and leaks no internals. No Cypher is constructed or interpolated. |
| **VII. Simplicity & Maintainability** | ✅ Pass | One parameter on an existing kind replaces a new attribute kind + graph label + index + migration + GraphQL type + frontend components. Extends the established per-kind parameters pattern rather than inventing one. No new abstractions, no new helpers, no new dependencies. |

**Post-design re-evaluation**: unchanged. Phase 1 design added no new components, no new
abstractions, and no new dependencies. The frontend finding (R6) *reduced* scope relative to the
pre-research plan, which strengthens VII. The Principle III deviation is unchanged in nature and
remains the single justified one.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Principle III**: `IPHost.value`'s serialised form becomes conditional on `parameters.allow_prefix` — the same attribute kind can return `10.0.0.1` or `10.0.0.1/32` depending on schema | The user need is exactly "the same IP type, without the invented mask". Any design that keeps serialisation unconditional must introduce a second type. | **A separate `IPAddress` attribute kind** (the withdrawn PR #9970) keeps `value` unconditional but cannot deliver the conversion customers need: `AttributeKindChecker` validates every existing value against the new kind's `validate_format`, which rejects any `/`, and every stored `IPHost` value carries a mask — so 100% of rows fail. The reverse direction is worse: it passes validation, the migration no-ops (`attribute_kind_update.py` returns early unless `is_large_attribute_type` differs, which it does not between these kinds), and leaves an attribute whose value has no mask and whose storage lacks `prefixlen` — silent corruption. Building per-transition kind gating is machinery that does not exist. |

**Mitigations that keep the deviation as narrow as possible** (all are requirements, not aspirations):

1. The declaration lives in `IPHostAttributeParameters`, not on `AttributeSchema`. The *schema*
   contract stays properly typed: the field is **unreachable** on other kinds by construction
   (`extra="forbid"`), not merely validated away.
2. Derived properties stay truthful. `prefixlen`/`netmask`/`with_netmask` return `32`/`128`-derived
   values rather than becoming null or meaningless (R3).
3. FR-011 keeps the SDK from advertising a type it no longer returns — the conditional form does not
   leak as a type lie.
4. Immutability (`NOT_SUPPORTED`) means an attribute's serialised form cannot change under existing
   data.

Per Governance, this deviation **must also be restated in the PR description**.

## Project Structure

### Documentation (this feature)

```text
specs/infp-551-bare-ip-attribute/
├── spec.md                    # /speckit-specify output
├── plan.md                    # This file
├── research.md                # Phase 0
├── data-model.md              # Phase 1
├── quickstart.md              # Phase 1
├── contracts/                 # Phase 1
│   ├── schema-contract.md     #   attribute-parameters contract + author-facing schema shape
│   └── sdk-contract.md        #   SDK value type + generated protocol annotation
├── checklists/
│   └── requirements.md
└── tasks.md                   # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/
│   ├── schema/
│   │   ├── attribute_parameters.py          # + IPHostAttributeParameters; register in
│   │   │                                    #   get_attribute_parameters_class_for_kind
│   │   ├── attribute_schema.py              # + IPHostAttributeSchema; register in
│   │   │                                    #   attribute_schema_class_by_kind; + validate_parameters guard
│   │   ├── definitions/internal.py          # + IPHostAttributeParameters in the `parameters`
│   │   │                                    #   SchemaAttribute internal_kind list
│   │   └── generated/attribute_schema.py    # REGENERATED (do not hand-edit)
│   ├── attribute.py                         # IPHost.validate_format + IPHost._normalize_value
│   │                                        #   become parameter-aware
│   └── protocols.py                         # REGENERATED

backend/tests/                                       # paths verified against the current layout
├── unit/core/schema/
│   └── test_iphost_attribute_parameters.py          # NEW — parameters/schema types: defaults, kind
│                                                   #   guard, NOT_SUPPORTED classification,
│                                                   #   default_value normalisation (pure Pydantic)
├── component/core/
│   ├── test_attribute_iphost_allow_prefix.py        # NEW — validation + normalisation matrix, DB
│   │                                               #   round trip, uniqueness, containment,
│   │                                               #   profile/template, branch merge, bare default,
│   │                                               #   kind-change silent drop
│   └── schema_manager/test_manager_schema.py        # EXTEND — schema-load guards
├── component/graphql/queries/
│   └── test_hfid.py                                 # EXTEND — mirrors the existing
│                                                   #   test_iphost_hfid_roundtrip_via_graphql (#8896)
├── integration/schema_lifecycle/
│   └── test_attribute_parameters_update.py          # EXTEND — toggle rejection (FR-009); this file
│                                                   #   already exists for parameter update support
└── integration_docker/
    └── test_computed_attributes.py                  # EXTEND — computed attribute + display-label
                                                    #   template receive the bare value

# Note: attribute validate_format/_normalize_value tests live at component level by existing
# convention (backend/tests/component/core/test_attribute.py), because constructing an attribute
# instance requires node/branch/at fixtures. Only the pure Pydantic schema-type tests are unit-level.

frontend/app/
├── src/                                     # NO source changes (see research.md R6)
├── src/shared/components/form/utils/
│   └── getFormFieldFromAttribute.test.ts    # + regression test: no prefix control for IPHost
└── tests/e2e/                               # + E2E: enter 10.0.0.1/32, see 10.0.0.1 everywhere

python_sdk/infrahub_sdk/                     # SEPARATE REPO — lands upstream first
├── node/attribute.py                        # value coercion consults parameters for IPHost;
│                                            #   remove the unreachable "IPAddress" kind key
├── protocols_generator/generator.py         # _jinja2_filter_render_attribute emits IPAddress[Optional]
│                                            #   for flagged IPHost attributes
├── protocols.py                             # REGENERATED
└── schema/generated/read.py                 # REGENERATED (adds IPHostAttributeParametersRead)

schema/schema.graphql                        # REGENERATED
schema/openapi.json                          # REGENERATED
docs/docs/reference/schema/                  # REGENERATED (attribute-kinds reference)
changelog/                                   # + Towncrier fragment
```

**Structure Decision**: this is a cross-cutting schema feature, not a new component, so it follows
the existing layout rather than introducing directories. Per
`.agents/rules/backend-component-design.md`, no new component/DI wiring is warranted: the change
extends two existing Pydantic models and two methods on an existing attribute class. The rule's
"do not refactor nearby non-conforming code as part of an unrelated change" clause applies —
`IPHost`'s `to_db`/model-hosted persistence shape is legacy and stays as it is.

## Implementation Phases

### Phase A — Backend schema types (blocks everything)

1. `IPHostAttributeParameters(AttributeParameters)` with
   `allow_prefix: bool = Field(default=True, description=..., json_schema_extra={"update": UpdateSupport.NOT_SUPPORTED.value})`.
   Default `True` is what guarantees FR-012: every existing schema parses to the pre-feature
   behaviour.
2. Register `"IPHost": IPHostAttributeParameters` in `get_attribute_parameters_class_for_kind`.
3. `IPHostAttributeSchema(AttributeSchema)` with the typed `parameters` field, mirroring
   `TextAttributeSchema`. Register `"IPHost": IPHostAttributeSchema` in
   `attribute_schema_class_by_kind`.

   **Registration is load-bearing, not bookkeeping.** `basenode_schema.py:152-174` upgrades every
   attribute — dict or instance — to its per-kind class via `get_attribute_schema_class_for_kind`.
   That is the mechanism which makes `parameters.allow_prefix` reachable from `validate_format` and
   `_normalize_value`; the defensive `getattr` in step 7 is belt-and-braces for base-classed instances
   on inherited, profile, and template paths, not the primary path.
4. Add the reverse guard to `AttributeSchema.validate_parameters`:
   `IPHostAttributeParameters` on a non-`IPHost` kind raises, matching the three existing branches.
5. Add a model validator to `IPHostAttributeSchema` that normalises `default_value`: when
   `allow_prefix` is `False` and the declared default carries a redundant host mask, strip it, so the
   schema records `10.0.0.1` rather than `10.0.0.1/32`.

   **Why this is required.** `SchemaBranch.validate_default_values()`
   (`schema_branch.py:1048-1066`) already routes defaults through
   `validate_format(value=node_attr.default_value, name=node_attr.name, schema=node_attr)`, and step 3
   guarantees `node_attr` is the per-kind class — so a **non-host-prefix** default starts being
   rejected at schema-load time for free once step 7 lands. But `_normalize_value` is an
   attribute-*instance* method and never runs against `schema.default_value`, so a `/32` default would
   be accepted and stored verbatim. The schema would then advertise `10.0.0.1/32` as the default for
   an attribute whose every node stores `10.0.0.1`. Normalising here mirrors FR-004 exactly, keeps the
   schema self-consistent, and touches no shared schema-processing pass.
6. Add `IPHostAttributeParameters` to the `internal_kind` list at `internal.py:806-812`.

**Gate**: `uv run invoke backend.generate` produces a diff confined to the `parameters` type union.

### Phase B — Backend behaviour (the one deep change)

7. `IPHost.validate_format`: after the existing `ip_interface(value)` check, when the schema declares
   `allow_prefix=False` and the supplied value carries a prefix that is not the host length for its
   version, raise `ValidationError({name: <message naming the attribute and stating a prefix is not permitted>})`.
   Read the parameter defensively — `getattr(schema.parameters, "allow_prefix", True)` — because
   `validate_format` receives the base `AttributeSchema` type and inherited/profile paths may pass a
   base-classed instance.
8. `IPHost._normalize_value`: return `str(ip_interface(value).ip)` when the flag is off, else keep
   `ip_interface(value).with_prefixlen` exactly as today.

**Ordering note**: 7 before 8 is not required for correctness — `__init__` runs `validate()` then
`_normalize_value()` (`attribute.py:166-167`) — but 7 must exist before 8 is tested, or a `/24` input
would silently normalise to a bare address instead of being refused.

**Side effect to expect**: step 7 also changes schema-load behaviour, because
`validate_default_values()` calls the same `validate_format`. A flagged attribute declaring
`default_value: "10.0.0.1/24"` will fail to load with a `default value ...` error. This is desired
(FR-003, FR-004) and must be asserted, not discovered.

**Gate**: the full existing `IPHost` suites pass untouched (FR-012).

### Phase C — Generated artefacts

9. `uv run invoke backend.generate`, `uv run invoke schema.generate-graphqlschema`,
   `uv run invoke schema.generate-jsonschema`, `uv run invoke docs.generate`, and
   `cd frontend/app && pnpm codegen`. Commit everything they touch.

**Gate**: `uv run invoke docs.validate` is clean — CI's `validate-generated-documentation` job fails
on a stale generated doc.

### Phase D — SDK (separate repo; pushed before the pointer moves, merged before Infrahub merges)

10. `node/attribute.py`: replace the kind-keyed `value_mapper` lookup with one that, for `IPHost`,
    consults `self._schema.parameters` and selects `ipaddress.ip_address` when `allow_prefix` is
    `False`, `ipaddress.ip_interface` otherwise. Remove the now-unreachable `"IPAddress"` kind key.
11. `protocols_generator/generator.py`: `_jinja2_filter_render_attribute` emits `IPAddress` /
    `IPAddressOptional` for a flagged `IPHost` attribute and `IPHost` / `IPHostOptional` otherwise.
    `ATTRIBUTE_KIND_MAP`, the protocol base classes, and the template imports already carry both.
12. Regenerate the SDK's `protocols.py` and `schema/generated/read.py`.

**Gate**: the SDK commit is **pushed** to `origin` in `infrahub-sdk-python`. That is enough for the
`python_sdk` pointer to move provisionally — root `AGENTS.md` § Submodules permits "merged *or the
commit is otherwise available upstream*", and a pushed PR branch is fetchable by every checkout. The
SDK **merge** gates only the Infrahub PR's own merge, not the pointer: before Infrahub merges, re-point
to the merged commit and verify it is an ancestor of `origin/infrahub-develop`, because a squash or
rebase on the SDK side can orphan the PR-branch commit.

### Phase E — Tests

Per the spec's Testing Strategy, **every** test pairs a declared attribute with an undeclared one,
because regression is the primary risk. Detailed breakdown lands in `tasks.md`; the levels are fixed
here:

- **Backend unit**: validation × normalisation × {bare, `/32`, `/128`, `/24`, `/64`, `/31`, `/0`} ×
  {IPv4, IPv6} × {declared, undeclared}; optional-attribute null path; `IPHostAttributeParameters`
  default and kind guard; the `NOT_SUPPORTED` classification; **`default_value` handling** — a `/32`
  default is recorded bare, a `/24` default fails schema load, and an undeclared attribute's default is
  untouched.
- **Backend component**: DB round trip; HFID round-trip lookup (mirroring the #8896 repro); uniqueness
  collision between the two input forms; prefix-containment query still returning a flagged value and
  `prefixlen == 32`; schema update flipping the flag rejected with `parameters.allow_prefix` named;
  profile and template node behaviour; branch-merge propagation of both the declaration and its
  validation behaviour; two branches setting `10.0.0.1` and `10.0.0.1/32` producing no conflict;
  **a node created with no explicit value receiving the bare default**; **the kind-change-away-from-`IPHost`
  silent drop**, pinning today's behaviour so a future change to it is deliberate.
- **Computed attributes and templates**: a flagged attribute referenced by a computed attribute and by
  a display-label Jinja2 template yields the bare value. Per Constitution Principle IV, features
  involving computed attributes require Integration Docker coverage, so this lands in
  `backend/tests/integration_docker/` rather than as a component test.
- **Frontend unit**: regression test asserting an `IPHost` attribute's form field carries no
  prefix-length control. This is a **requirement guard for FR-010**, not optional polish — FR-010 is
  currently satisfied only incidentally (R6), and this test is the sole thing standing between a future
  dedicated IPHost input and a silent FR-010 violation.
- **E2E**: the spec's scenario, end to end.
- **SDK unit**: flagged attribute yields `IPv4Address`/`IPv6Address`; undeclared yields
  `IPv4Interface`/`IPv6Interface`; protocol generation emits the right annotation for each.

### Phase F — Documentation and changelog

13. Document `allow_prefix` on the attribute-kinds reference page (regenerated — the source is the
    field `description`, so write that description carefully).
14. User-facing documentation of the bare-address declaration under `docs/`, covering:
    - the immutability restriction, and that in-place conversion is the tracked follow-up;
    - **a manual conversion recipe for an existing populated `IPHost` attribute**: add a new
      bare-address attribute alongside the old one, backfill it through the SDK, repoint
      `display_labels` / `human_friendly_id` / uniqueness constraints, then remove the old attribute.
      Without this, "conversion is a manual exercise for v1" is an assumption with no path behind it,
      and the likeliest customer — one whose *existing* field acquired a mask from the #8896 fix — is
      left to infer it;
    - that a schema author should set the attribute's `description`, since the UI surfaces it as field
      help text and it is the only pre-submit affordance telling an operator a prefix is disallowed
      (there is no IPHost-specific input component — R6);
    - the SDK version floor, and that an older SDK re-attaches the host mask.
15. Towncrier fragment in `changelog/`.

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Inherited / profile / template attributes reach `validate_format` with a base-classed `AttributeSchema`, so `schema.parameters` lacks `allow_prefix` and the flag is silently ignored | Medium | Per-kind class registration (Phase A step 3) is the primary defence; the defensive `getattr(..., True)` read (Phase B step 7) is the fallback, **plus** an explicit component test on profile and template nodes. This is the highest-value test in the set: silent flag loss is the failure mode that would look like the feature working. |
| **Rollback**: reverting the code after customers have stored bare values leaves **mixed stored forms** — existing rows stay bare while new writes re-acquire `/32`, and stored HFIDs and display labels diverge accordingly | Low | No data action is needed and no read breaks (`ip_interface("10.0.0.1")` still parses and every derived property still resolves), so a revert is safe but not clean. The practical rollback unit is the **schema declaration**, not the code: flip the attribute back only through the tracked follow-up that rewrites stored values. Document this alongside the immutability restriction. |
| `set_parameters_type` silently drops `allow_prefix` on a kind change away from `IPHost` | Certain (by design) | Accepted and documented for v1, per the spec's Out of Scope. Covered by a test that pins the *current* behaviour so a future change to it is deliberate. |
| Core-schema diff makes `infrahub upgrade` fail locally on the known Prefect flow-parameter size limit | High, local only | Documented in quickstart.md with the `PREFECT_SERVER_API_MAX_PARAMETER_SIZE=0` workaround. Not a product defect. |
| Submodule pointer references a commit no checkout can fetch, breaking every fresh clone | Low | Two distinct failure modes, two gates. **Unpushed commit**: Phase D's push gate. **Orphaned commit** — the subtler one: pointing at an SDK PR-branch commit is safe during review, but a squash/rebase on SDK merge plus branch deletion can leave it unreferenced, so the pointer must be moved to the merged commit and verified as an ancestor of `origin/infrahub-develop` before the Infrahub PR merges. |
| A future dedicated IPHost input component reintroduces a prefix control, violating FR-010 unnoticed | Medium, deferred | The frontend regression test added in Phase E is precisely the guard. |

## Generated Artefacts (never hand-edited)

`backend/infrahub/core/schema/generated/`, `backend/infrahub/core/protocols.py`,
`schema/schema.graphql`, `schema/openapi.json`,
`frontend/app/src/shared/api/graphql/generated/`, `frontend/app/src/shared/api/rest/types.generated.ts`,
`docs/docs/reference/schema/`, `python_sdk/infrahub_sdk/protocols.py`,
`python_sdk/infrahub_sdk/schema/generated/read.py`.

Regeneration commands are listed in Phase C and Phase D.
