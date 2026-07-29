---

description: "Task list for bare IP addresses on IPHost attributes"
---

# Tasks: Bare IP addresses on IPHost attributes

**Input**: Design documents from `specs/infp-551-bare-ip-attribute/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md),
[critiques/critique-20260728-152234.md](./critiques/critique-20260728-152234.md)

**Tests**: Included. The spec carries a mandatory Testing Strategy section and Constitution
Principle IV requires tests at the appropriate level for every feature.

**Organization**: Tasks are grouped by user story. Note the ship order below — it is **not** the same
as the priority-label order, because the spec explicitly states US3 (SDK) ships *with* US1 while US2
(UI) ships *after* it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in every task

## Path Conventions

Web application spanning three trees:

- **Backend**: `backend/infrahub/`, tests in `backend/tests/{unit,component,integration,integration_docker}/`
- **Frontend**: `frontend/app/src/`, E2E in `frontend/app/tests/e2e/`
- **SDK**: `python_sdk/infrahub_sdk/` — **separate repository** (submodule), tests in `python_sdk/tests/unit/`

## Standing Rules

- **Every behavioural test pairs a declared (`allow_prefix: false`) attribute with an undeclared one.**
  Regression, not absence, is the primary risk (spec Testing Strategy).
- **Never hand-edit generated files.** See the plan's Generated Artefacts list; regenerate instead.
- **No commits or pushes without explicit instruction.** Leave work in the working tree and report.
- Per `.agents/rules/code-doc-style.md`, do **not** reference `INFP-551`, `FR-0xx`, or task IDs in
  source, docstrings, comments, or test names. Those IDs belong in commit messages, the changelog
  fragment, and these spec files only.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the regression baseline and the shared test fixture before any code changes.

- [X] T001 Record the FR-012 / SC-006 baseline: run the existing IPHost-touching suites on the
  unmodified tree and save the results to `/tmp/iphost-baseline.txt` —
  `uv run pytest backend/tests/component/core/test_attribute.py backend/tests/component/graphql/queries/test_hfid.py backend/tests/unit/test_types.py -v`.
  Every later phase is measured against this.
- [X] T002 [P] Add the shared test schema fixture carrying **both** attribute flavours (a
  bare-address `dns_target` with `unique: true`, an undeclared `mgmt_ip` control, and a bare-address
  IPv6 `v6_target`) to `backend/tests/fixtures/` following the existing schema-fixture convention;
  reuse an existing fixture instead if one already provides an `IPHost` attribute plus `display_labels`
  and `human_friendly_id`. The exact shape is in `quickstart.md` § Test schema fixture.

**Checkpoint**: Baseline captured; fixture available to every story.

### Phase 1 implementation notes

- **T001 result**: 76 passed, 0 failed on the unmodified tree at commit `8925db53b`; no
  pre-existing failures to work around. `/tmp/iphost-baseline.txt` carries a provenance header
  (timestamp, commit, command, DB) above the verbatim `-v` output.
- **T002 landed at `backend/tests/helpers/schema/dns_record.py`, not `backend/tests/fixtures/`.**
  No existing fixture provided `IPHost` + display label + `human_friendly_id`, so reuse was not an
  option. `backend/tests/fixtures/schemas/` is JSON-only, contains zero `human_friendly_id`
  precedent, has no YAML loader, and is reachable only through the conftest-scoped `helper` pytest
  fixture — unusable at import time for parametrised unit tests. `backend/tests/helpers/schema/` is
  the actual convention for shared schema fixtures of this shape and already ships a `load_schema()`
  helper. Exported as `DNS_RECORD_DEFINITION` (raw dict), `DNS_RECORD_SCHEMA` (`SchemaRoot`), and
  `DNS_RECORD` (`NodeSchema`).
- **Uses `display_label` (singular), not `display_labels`.** `display_labels` is deprecated and
  emits a warning; the singular field accepts the same attribute path.
- **The fixture is a raw dict, deliberately.** Attribute parameters are coerced from dicts by a
  `mode="before"` validator, so the dict form drives the same path a user's YAML/JSON payload takes.
  It is also the only mypy-clean spelling until an `IPHost` parameters model joins the `parameters`
  union — CI runs `mypy backend`, and `backend/tests/helpers/` is not excluded.
- **`generate_template=True` was added beyond the quickstart shape** so Scenario 5 has profile and
  object-template kinds to assert against.
- **Scenario 5 must assert on `v6_target`, not `dns_target`.** Verified: `dns_target` is absent from
  both `ProfileTestingDnsRecord` (`mgmt_ip`, `profile_name`, `profile_priority`, `v6_target`) and
  `TemplateTestingDnsRecord` (`mgmt_ip`, `template_name`, `v6_target`) because unique attributes are
  excluded from both generated kinds.
- **`allow_prefix` is silently dropped today**, not rejected: `AttributeParameters.convert_from_dict`
  filters unknown keys before pydantic's `extra="forbid"` sees them, and `IPHost` has no entry in
  `get_attribute_parameters_class_for_kind`. So the fixture loads clean pre-feature, and a test
  asserting rejection of the flag would fail until the parameters model lands.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Make the declaration exist and be published. Corresponds to plan Phase A plus the backend
half of plan Phase C.

**⚠️ CRITICAL**: No user story can begin until this phase completes — US1 needs the parameter to read,
US2 and US3 need it published in the schema contract.

- [X] T003 Add `IPHostAttributeParameters(AttributeParameters)` with
  `allow_prefix: bool = Field(default=True, description=..., json_schema_extra={"update": UpdateSupport.NOT_SUPPORTED.value})`
  to `backend/infrahub/core/schema/attribute_parameters.py`. The `description` text becomes the
  attribute-kinds reference documentation, so write it for a schema author. Default `True` is what
  guarantees FR-012.
- [X] T004 Register `"IPHost": IPHostAttributeParameters` in
  `get_attribute_parameters_class_for_kind` in
  `backend/infrahub/core/schema/attribute_parameters.py` (depends on T003).
- [X] T005 Add `IPHostAttributeSchema(AttributeSchema)` carrying the typed
  `parameters: IPHostAttributeParameters` field (mirroring `TextAttributeSchema`) and register
  `"IPHost": IPHostAttributeSchema` in `attribute_schema_class_by_kind`, both in
  `backend/infrahub/core/schema/attribute_schema.py` (depends on T003).
  **Registration is load-bearing**: `backend/infrahub/core/schema/basenode_schema.py:152-174` upgrades
  every attribute to its per-kind class, which is what makes `parameters.allow_prefix` reachable from
  the attribute class.
- [X] T006 Add the reverse guard to `AttributeSchema.validate_parameters` in
  `backend/infrahub/core/schema/attribute_schema.py` — an `IPHostAttributeParameters` instance on a
  non-`IPHost` kind raises `"IPHostAttributeParameters can't be used as parameters for {kind}"`,
  matching the three existing branches at lines 157-166 (depends on T003).
- [X] T007 Add a model validator to `IPHostAttributeSchema` in
  `backend/infrahub/core/schema/attribute_schema.py` that strips a redundant host mask from
  `default_value` when `allow_prefix` is `False`, so the schema records `10.0.0.1` rather than
  `10.0.0.1/32` (depends on T005). Without this the schema advertises a default that no node ever
  receives — see critique E1.
- [X] T008 Add `IPHostAttributeParameters` to the `internal_kind` list of the `parameters`
  `SchemaAttribute` at `backend/infrahub/core/schema/definitions/internal.py:803-817` (depends on
  T003). This is the single edit that produces the core-schema diff.
- [X] T009 Regenerate backend artefacts — `uv run invoke backend.generate` — and commit the resulting
  changes to `backend/infrahub/core/schema/generated/` and `backend/infrahub/core/protocols.py`
  (depends on T008). **Verify the diff is confined to the `parameters` type union**; anything wider
  means a mistake in T003-T008.
- [X] T010 [P] Write the schema-type unit tests in
  `backend/tests/unit/core/schema/test_iphost_attribute_parameters.py`: `allow_prefix` defaults to
  `True`; `allow_prefix` on a `Text` attribute is rejected by `extra="forbid"`;
  `IPHostAttributeParameters` on a non-`IPHost` kind raises; the field carries
  `UpdateSupport.NOT_SUPPORTED`; a `/32` `default_value` is normalised to bare and a bare one is left
  alone; an undeclared attribute's `default_value` is untouched (depends on T003-T007).
- [X] T011 Confirm the baseline still holds — re-run the T001 command and diff against
  `/tmp/iphost-baseline.txt`. Schema types alone must change no behaviour.

**Checkpoint**: The declaration exists, is guarded on other kinds, is immutable by classification, and
is published in the schema contract. All three stories can now proceed.

### Phase 2 implementation notes

- **T008 was not a single edit — `backend.generate` refuses to run until three more places agree.**
  The generator is deliberately fail-closed: `_attribute_kinds_by_parameters`
  (`tasks/backend.py`) compares the backend's kind → parameters mapping against the SDK generator's
  `attribute_variant_specs` and raises when they diverge. So publishing the class needed:
  1. the `internal_kind` list entry (T008 as written);
  2. `from ... import IPHostAttributeParameters` in `backend/templates/attributeschema_imports.j2` —
     the generated module's import block comes from this hand-maintained template, not from the
     `internal_kind` list, so without it the generated file references an undefined name;
  3. `("IPHostAttribute", "IPHostAttributeParameters")` in `attribute_variant_specs`, an
     `IPHostAttributeParameters{suffix}` entry in `_pre_families`, and an `iphost_parameters_fields`
     field list, all in `tasks/backend.py`.
- **T009 diff scope.** `backend/infrahub/core/schema/generated/attribute_schema.py` gained exactly two
  lines — the import and the union member. `backend/infrahub/core/protocols.py` is unchanged.
  `backend.generate` also writes the SDK's `python_sdk/infrahub_sdk/schema/generated/{read,write}.py`,
  which gained `IPHostAttributeParameters{Read,Write}` and `IPHostAttribute{Read,Write}` and moved
  `AttributeKind.IPHOST` out of the generic variant — exactly what `data-model.md` predicted. **Those
  changes are left uncommitted in the submodule working tree**; the submodule pointer was not moved.
  T030/T032/T033 own the SDK commit.
- **`schema/schema.graphql`, `schema/openapi.json` and the generated docs were deliberately not
  regenerated** — that is T023, and no test or CI job in this repo checks them before then.
- **The `allow_prefix` description had to be short.** The first draft (five sentences covering both
  flag states, an example, and the immutability restriction) made the generated SDK line 476
  characters and failed `ruff` E501 at 150. The description is duplicated verbatim in
  `tasks/backend.py`, so the practical ceiling is ~127 characters. The fuller explanation belongs in
  the user-facing documentation (T038), not the field description.
- **T010's `extra="forbid"` expectation was wrong as written, and the contract is wrong with it.**
  `allow_prefix` declared on a `Text` attribute in a loaded schema is **silently dropped**, not
  rejected: `set_parameters_type` coerces the mapping through
  `TextAttributeParameters.convert_from_dict`, which filters unknown keys before `extra="forbid"`
  can see them. `extra="forbid"` only fires when a parameters model is built from the mapping
  directly. Both behaviours are now pinned by tests, but
  `contracts/schema-contract.md` § Rejection cases (rows 1-2) overstates what happens, and the
  note claiming FR-002 "needs no implementation task" holds only for the reverse direction.
  This is pre-existing behaviour shared by every attribute parameter (`regex` on a `Number`
  attribute is dropped the same way), so it was left alone rather than fixed inside this phase.
- **The reverse guard (T006) only fires on kinds with no registered parameters class** — `Boolean`,
  `IPNetwork`, `Dropdown`, … For `Text` or `Number`, `set_parameters_type` converts the instance to
  that kind's own parameters class before `validate_parameters` runs, so the guard never sees it.
  This is identical to how the three pre-existing guards behave; the test parametrises over
  `Boolean` and `IPNetwork` accordingly.
- **T007 leaves a non-host prefix and an unparsable default untouched.** Only a redundant host mask
  is stripped, so `default value` reporting stays with the format validator that T017/T019 cover.

---

## Phase 3: User Story 1 — Author and populate a bare-address attribute (Priority: P1) 🎯 MVP

**Goal**: A schema author declares an `IPHost` attribute as holding a bare address, loads data through
the API, and every read path returns the address with no mask. Input carrying a real subnet prefix is
refused with an error naming the attribute.

**Independent Test**: Load the T002 fixture, create nodes through the API in each input form, and
assert the stored value, API response, display label, and human-friendly identifier. No UI and no SDK
change required.

### Tests for User Story 1

> Write these first and confirm they fail before T017-T018.

- [X] T012 [P] [US1] Write the validation and normalisation matrix in
  `backend/tests/component/core/test_attribute_iphost_allow_prefix.py`: {bare, `/32`, `/128`, `/24`,
  `/64`, `/31`, `/0`} × {IPv4, IPv6} × {declared, undeclared}. Declared rejects every non-host prefix
  with an error naming the attribute; declared stores bare for bare and host-mask input; undeclared
  behaves exactly as today. Include the optional-attribute null path (no prefix logic applied).
- [X] T013 [P] [US1] Write the storage and derived-property assertions in the same file: for a
  declared attribute the stored `value` is bare **and** the value vertex still carries
  `prefixlen == 32` (IPv4) / `128` (IPv6), `binary_address`, and `version`; an IPAM prefix-containment
  query for `10.0.0.0/8` still returns the node. This test guards FR-008 against a future "clean up
  the meaningless prefixlen" refactor.
- [X] T014 [P] [US1] Extend `backend/tests/component/graphql/queries/test_hfid.py` with a
  bare-address counterpart to the existing `test_iphost_hfid_roundtrip_via_graphql` (the #8896
  reproduction): the HFID and display label carry no mask, and the HFID returned by a query is
  accepted verbatim as lookup input with zero caller-side transformation.
- [X] T015 [P] [US1] Write the uniqueness collision test in
  `backend/tests/component/core/test_attribute_iphost_allow_prefix.py`: on a declared attribute with a
  uniqueness constraint, nodes created with `10.0.0.1` and `10.0.0.1/32` collide. Assert the same two
  inputs also collide on an undeclared attribute (both store `10.0.0.1/32`), so the test distinguishes
  the new behaviour from the old.
- [X] T016 [P] [US1] Extend
  `backend/tests/integration/schema_lifecycle/test_attribute_parameters_update.py` with the toggle
  rejection (FR-009): flipping, adding, or removing `allow_prefix` on an existing attribute fails with
  an unsupported-change error naming `parameters.allow_prefix`.

### Phase 3 test notes (T012-T016)

**Expected-fail state.** T012-T015 were written before T017/T018 and are red on purpose. Verified
`2026-07-28`, 15 failing / 20 passing across the two component files:

- `backend/tests/component/core/test_attribute_iphost_allow_prefix.py` — 14 failed, 19 passed.
  Failures: 4 stored-value assertions (`'10.0.0.1/32' == '10.0.0.1'`), 9 `DID NOT RAISE
  ValidationError` on non-host prefixes, 1 uniqueness test failing on its stored-value precondition.
- `backend/tests/component/graphql/queries/test_hfid.py::test_bare_iphost_hfid_roundtrip_via_graphql`
  — 1 failed on `'192.0.2.10/32' == '192.0.2.10'`.
- The undeclared-control halves all pass today, as does the whole of T016.

**T016 passes now, by design.** The notes below "Three requirements need no implementation task"
already predicted this: the diff walker honours the sub-field's own `NOT_SUPPORTED` classification, so
flipping, removing, and adding `allow_prefix` are all already refused. T016 is a verification task.

**Gap found by T016: the rendered error does not name the parameter.**
`SchemaUpdateValidationError.to_string()` (`backend/infrahub/core/models.py:141-142`) formats only
`error`, `schema_kind`, `field_name`, and `message` — it drops `path.property_name`. So the HTTP 422
body reads `'not_supported': TestingDnsRecord dns_target None`, which identifies the attribute but not
the declaration. FR-009's "error identifying the declaration" is therefore only half-met at the API
surface. The test pins the message as produced **and** asserts
`path.property_name == "parameters.allow_prefix"` against `validate_update` directly, so the
requirement is verified where it currently holds. **Follow-up**: including `property_name` in
`to_string()` is a one-line production change that would improve every `not_supported` and
`migration_not_available` message; it was left out of a tests-only chunk because it changes error text
shared with other suites.

**Rejection message pinned by the tests.** T017 has no wording yet, so the tests define it:

```text
{value} is not a valid IPHost because a subnet prefix is not permitted
```

raised as `ValidationError({attribute_name: ...})`, which the dict formatter renders as
`... is not permitted at dns_target`. T017 must use this exact string or update the tests with it.

**Matrix decisions where the target behaviour was ambiguous.**

- `/0` and `/31` (IPv4) — **rejected**. The spec's Edge Cases are explicit that any prefix other than
  the host length is refused.
- IPv6 `/64` and `/127` — **rejected**, same rule, `/127` being the IPv6 analogue of `/31`.
- IPv6 `/32` — **rejected**. Not named in the spec, but 32 is a subnet prefix for IPv6; the check is
  the parsed prefix length against the version's host length, never a literal `32`. This case exists
  precisely to catch an implementation that hardcodes `32`.
- IPv4 `/128` — **not** a prefix-policy case. `ip_interface("10.0.0.1/128")` raises, so both declared
  and undeclared attributes keep today's `is not a valid IPHost` error. Included so the matrix does not
  imply the new rule swallowed the malformed-input path.
- `10.0.0.1/255.255.255.0` (netmask notation) — **not covered**. `ip_interface` resolves it to `/24`,
  so it is already covered by the `/24` row; adding it would assert the same code path twice.

**Prefix containment is asserted against the value vertex, not through IPAM.** The IPAM containment
queries are scoped to IPAM node kinds and attribute names, so they never see a `TestingDnsRecord`
attribute. The test instead runs the same predicate those queries use —
`av.binary_address STARTS WITH <the /8 bit prefix>` on the `AttributeIPHost` vertex — for both the
declared and the undeclared attribute. This passes today and must keep passing once storage goes bare,
which is the FR-008 guard the task asked for.

**T015 needed a schema variant.** The shared fixture's `mgmt_ip` control is not unique, so the
undeclared half of the collision test had nothing to collide on. The test derives a variant with
`deepcopy` marking `mgmt_ip` unique rather than changing the shared fixture. Note that the *collision*
itself already happens today (both input forms normalise to `10.0.0.1/32`), so what distinguishes new
from old is the value quoted in the violation message —
`An object already exist with this value: dns_target: 10.0.0.1` — plus the stored-value precondition.

**`display_label` was added to the new HFID test's query.** The existing
`test_iphost_hfid_roundtrip_via_graphql` was not touched, in line with T024.

### Implementation for User Story 1

- [X] T017 [US1] Make `IPHost.validate_format` parameter-aware in
  `backend/infrahub/core/attribute.py:1130-1148`: after the existing `ip_interface(value)` check, when
  the schema declares `allow_prefix=False` and the parsed interface's `network.prefixlen` is not the
  host length for its version (32 / 128), raise `ValidationError` keyed by the attribute `name` with a
  message stating a subnet prefix is not permitted. Read the flag as
  `getattr(schema.parameters, "allow_prefix", True)` — the method is typed against the base
  `AttributeSchema` and inherited/profile/template paths may pass a base-classed instance.
  **Check the parsed prefix length, never the presence of `/` in the string**, or `/32` would be
  wrongly refused.
- [X] T018 [US1] Make `IPHost._normalize_value` parameter-aware in
  `backend/infrahub/core/attribute.py:1150-1151`: return `str(ipaddress.ip_interface(value).ip)` when
  the flag is off, else keep `ipaddress.ip_interface(value).with_prefixlen` exactly as today. Read the
  flag from `self.schema.parameters` (set at `attribute.py:120`, before the validate/normalise pair
  runs at `attribute.py:166-167`). Leave `to_db()` and every derived property untouched.
- [X] T019 [US1] Add the schema-load default-value tests to
  `backend/tests/component/core/schema_manager/test_manager_schema.py`: a declared attribute with
  `default_value: "10.0.0.1/24"` fails to load with a `default value ...` error naming the attribute
  (this falls out of T017 via `SchemaBranch.validate_default_values()` at
  `backend/infrahub/core/schema/schema_branch.py:1048-1066`), a `/32` default loads and is recorded
  bare, and a node created with no explicit value receives the bare default (depends on T007, T017).
### Phase 3 implementation notes (T017-T019)

- **The flag is read with `isinstance`, not `getattr`.** `dev/guidelines/backend/python.md` § "Prefer
  `isinstance` over `getattr` for narrowing" forbids the `getattr` spelling the task text suggested,
  and `attribute.py` already has the precedent one class up
  (`isinstance(schema.parameters, NumberAttributeParameters)` in `BaseAttribute.validate_content`),
  with `attribute_parameters` already imported at runtime so no import cycle is involved. The
  behaviour is identical to `getattr(..., "allow_prefix", True)`: a base-classed
  `AttributeParameters` fails the `isinstance` check and yields the permissive answer. Both call
  sites go through one private `IPHost._allows_prefix(schema=...)` staticmethod, so the classmethod
  validator and the instance-level normaliser cannot drift apart.
- **The host length is derived as `interface.ip.max_prefixlen`**, the same idiom T007 already uses on
  the schema side. `32`/`128` appear nowhere in the production change, so the IPv6-`/32` case is
  rejected for the right reason.
- **No committed test needed changing.** The error wording the Phase 3 test notes pinned was adopted
  verbatim; all 15 expected failures flipped and the 20 controls kept passing on the first run.
- **The profile/template/inherited path held no surprises.** `set_parameters_type` keys off `kind`,
  so any attribute with `kind: IPHost` — base `AttributeSchema` included — ends up carrying
  `IPHostAttributeParameters`. T020 still owns proving that end to end.
- **T019's rejection message reads**
  `InfraTinySchema: default value 10.0.0.1/24 is not a valid IPHost because a subnet prefix is not permitted at something`
  — the `{namespace}{name}: default value ` prefix from `validate_default_values()` wrapped around
  the dict-formatted `... at {attribute}` suffix.
- **T019 landed as two tests, one per tier.** The prefix-policy matrix is a parametrised dataclass
  case set beside the existing `test_validate_default_value_*` pair, running against an in-memory
  `SchemaBranch` with no DB (cheapest tier, and it pins the undeclared control's `/24` and `/32`
  defaults as untouched). The "a node with no explicit value receives the bare default" half needs
  the registry, so it loads a `default_value`-carrying variant of the shared fixture through
  `load_schema` and asserts `is_default` alongside the bare value.
- **Pre-existing local noise, not regressions.** `backend/tests/unit/git/test_git_repository.py` has
  3 failures with the change stashed as well as applied, and every `ty` diagnostic from
  `invoke backend.lint` points into the untracked `repositories/` scratch directory. `invoke lint`
  also reports yamllint errors in `development/docker-compose*.override.yml` and inside
  `python_testcontainers/.venv`, none of them tracked files.
- **`mypy` does not see the new tests.** `^backend/tests/component` is in `[tool.mypy].exclude`, so
  the 284 errors reported when pointing mypy at `test_manager_schema.py` directly (284 of them
  pre-existing) are not a CI gate. `backend/infrahub/core/attribute.py` is mypy-clean.

- [X] T020 [US1] Add the profile and template tests to
  `backend/tests/component/core/test_attribute_iphost_allow_prefix.py`: a profile node and a template
  node inheriting a declared attribute validate and serialise identically to the node they derive
  from. **This is the highest-value test in the set** — silent flag loss on these paths would look
  exactly like the feature working (plan Risks).
- [X] T021 [US1] Add the branch-merge tests to the same file: an attribute declared on a branch
  carries both the declaration **and** its rejection behaviour to the target branch after merge; and
  two branches setting `10.0.0.1` and `10.0.0.1/32` on the same declared attribute produce **no**
  merge conflict, because they converge on one stored value. Required by Constitution Principle II.
- [X] T022 [US1] Add the kind-change test to the same file, pinning today's behaviour: changing a
  declared attribute's kind away from `IPHost` silently drops `allow_prefix` (via
  `set_parameters_type` in `backend/infrahub/core/schema/attribute_schema.py:136-153`). The spec
  accepts this silence for v1; the test exists so a future change to it is deliberate.
- [X] T023 [US1] Regenerate the remaining contract artefacts and commit them:
  `uv run invoke schema.generate-graphqlschema`, `uv run invoke schema.generate-jsonschema`,
  `uv run invoke docs.generate`, and `cd frontend/app && pnpm codegen` (depends on T009).
- [X] T024 [US1] Verify the FR-012 gate: re-run the T001 command and confirm the results match
  `/tmp/iphost-baseline.txt` exactly. **Any modification needed to an existing IPHost test is a
  regression, not a test-maintenance task** — investigate rather than adjust the test.
- [X] T025 [US1] Verify `uv run invoke docs.validate` is clean, so CI's
  `validate-generated-documentation` job will pass (depends on T023).
- [X] T046 [US1] **Found by T021.** Normalise an attribute value on the *update* path, not only on
  construction. `BaseAttribute.__init__` was the sole caller of
  `_normalize_value` (`backend/infrahub/core/attribute.py:166-167`); `from_graphql` and a plain
  `attr.value = ...` assignment both set the value verbatim, and `_update`
  (`backend/infrahub/core/attribute.py:446`) re-validated but never re-normalised. Evidence, from a
  real `TestingDnsRecordUpdate` mutation against the shared fixture:

  ```text
  request:  dns_target = "10.0.0.9/32"   mgmt_ip = "10.0.0.9"
  response: dns_target = "10.0.0.9/32"   mgmt_ip = "10.0.0.9"   display_label = "10.0.0.9/32"
  graph:    dns_target = "10.0.0.9/32"   mgmt_ip = "10.0.0.9"
  ```

  So editing a declared attribute leaked the mask into the API response, the stored value, and the
  persisted display label — FR-005 held on create and failed on update.

  **Implemented as a `_normalize_assigned_value` hook**: a no-op on `BaseAttribute` that `IPHost`
  overrides to return the bare form *only* when `allow_prefix` is `False`. It is called from two
  seams. In `_update`, immediately after the existing `validate(...)`, so a value that arrived by a
  plain `attr.value = ...` assignment is canonical before it is written and before the changelog, the
  `is_default` comparison and the hfid/display-label recompute read it. In `from_graphql`, where the
  incoming value is set, so the pre-save uniqueness constraint and the mutation lock names compare the
  value that will actually be stored. The second seam was **proven necessary by test rather than
  assumed**: with only the `_update` seam, updating a declared unique attribute to `10.0.0.1/32` while
  another node held `10.0.0.1` passed the uniqueness check and wrote a duplicate. The hook validates
  before it normalises, so a rejected subnet prefix is still reported instead of being quietly
  rewritten into an address that would be accepted.

  **The scope was deliberately limited to a declared attribute.** Normalising unconditionally was
  considered and rejected: it would rewrite stored values for already-populated undeclared
  `IPHost`/`IPNetwork`/`MacAddress` attributes and need a migration, which FR-012 forbids. No shipped
  schema declares `allow_prefix: false`, so the production blast radius of the change is zero.

  **The general update-path normalisation gap remains open, and is worth its own ticket.** For an
  undeclared `IPHost`, an `IPNetwork` or a `MacAddress`, an edit still writes whatever spelling it was
  given: a bare `10.0.0.9` reaches the graph without its `/32`, and a mutation response echoes the raw
  input. It hides on a reload only because `__init__` re-normalises on the way out of the database, so
  the stored value and the read value disagree — which is also why a uniqueness check can miss a
  duplicate spelled the other way (observed: an undeclared unique attribute accepted `10.0.0.1` while
  `10.0.0.1/32` was already stored for it). `TestTheUpdatePath` pins that behaviour as it stands today,
  so changing it will be a deliberate act.

**Checkpoint**: US1 is fully functional and independently demonstrable. The MVP is complete — an author
can declare a bare-address attribute and every backend read surface returns no mask. Create, read,
update, profile, template, schema-merge, uniqueness and HFID paths all return no mask.

### Phase 3 implementation notes (T020-T025)

- **T020's answer to the plan's top risk: the profile and template paths do *not* lose the flag.**
  `set_parameters_type` keys off `kind`, so `ProfileTestingDnsRecord` and `TemplateTestingDnsRecord`
  both carry `IPHostAttributeParameters(allow_prefix=False)` on `v6_target` and the permissive default
  on `mgmt_ip`. A profile and a template each reject `2001:db8::1/64` with the same message a node
  does, store `2001:db8::1/128` as bare, and hand the bare value on to the node that derives from
  them — asserted through `NodeProfilesApplier.apply_profiles` and `NodeTemplateApplier.apply`
  respectively. `dns_target` is untestable here (unique attributes are excluded from both generated
  kinds), which is why every assertion is on `v6_target`.
- **T021 first half passes and follows the production merge path.** The graph merge writes the schema
  nodes; the destination schema is then re-read with `load_schema_from_db` and re-registered, exactly
  as the merge orchestrator does. Both the declaration and the rejection behaviour survive.
- **T021 second half was red for a production reason, not a test reason — fixed by T046.** The two
  input forms did not converge, because neither was normalised on the update path, so the diff saw
  `10.0.0.1` against `10.0.0.1/32` and reported a conflict. It passes on its original assertions now
  that an edit of a declared attribute is normalised. The paired assertions that *do* hold are
  kept in their own green test: genuinely different addresses conflict on the declared attribute and
  on the undeclared control alike, so the expected absence of a conflict cannot be confused with the
  enricher never looking at the attribute.
- **T022 pins the drop from both directions.** A schema payload re-loaded with `kind: Text` and a live
  `IPHostAttributeParameters` instance carried onto a `Text` attribute both end up with a bare
  `TextAttributeParameters`, silently; coming back to `IPHost` yields `allow_prefix=True`, not the
  declaration that was there before. The pairing is a re-parse that keeps the kind (only
  `description` changes), which keeps the declaration — so the cause is the kind change and nothing
  else about re-validation.
- **T023 diff is confined to `schema/openapi.json` plus the REST types it feeds.** Structurally: new
  `IPHostAttribute{Read,Write}` and `IPHostAttributeParameters{Read,Write}` components (the latter
  carrying `allow_prefix`, default `true`), `IPHost` dropped from `GenericAttribute{Read,Write}`'s
  `kind` enum, and the `oneOf` member plus discriminator mapping repointed for `IPHost` on
  `NodeSchema{Read,Write}`, `GenericSchema{Read,Write}`, `ProfileSchemaRead`, `TemplateSchemaRead` and
  `NodeExtensionWrite`. 227 leaf additions, 2 removals, 24 changes, zero unrelated churn.
- **`schema/schema.graphql` and the generated docs did not change at all.** The core schema exposes
  `parameters` as an opaque `JSON` attribute, so no per-kind parameters model reaches either surface.
  `docs.validate` is therefore clean without any doc edit — and **T039 will find that
  `allow_prefix` is not rendered anywhere in the schema reference**, because that page documents the
  `parameters` field itself rather than its per-kind contents. T038's hand-written page is the only
  place the flag can be documented today.
- **`pnpm codegen` is the wrong command for the REST types, and it fails for an unrelated reason.**
  `codegen` only regenerates the GraphQL types from `schema/schema.graphql` (unchanged here), and it
  exits non-zero on a pre-existing document-validation error in
  `frontend/app/src/shared/api/graphql/graphqlClientApollo.test.ts` ("This anonymous operation must be
  the only defined operation") — reproduced with this branch's changes stashed. The command that
  consumes `schema/openapi.json` is `pnpm codegen:openapi`; that is what regenerated
  `frontend/app/src/shared/api/rest/types.generated.ts`.
- **T024 gate is clean.** 77 passed; all 76 baseline node ids still `PASSED`, none missing, none
  changed status, one new id (`test_bare_iphost_hfid_roundtrip_via_graphql`, added by T014). No
  existing IPHost test was touched.

---

## Phase 4: User Story 3 — Consume it through the Python SDK (Priority: P3 — ships with P1)

**Goal**: An SDK consumer reads the attribute and receives a bare address object, and generated
protocols type it as a bare address rather than as an interface type.

**Why here and not last**: the spec labels this P3 because it is the narrowest slice, but requires it
to ship **alongside P1** — without it the SDK re-attaches the host mask to a bare stored value and
directly contradicts FR-005 and FR-011.

**⚠️ SEPARATE REPOSITORY**: T026-T031 modify `python_sdk/`, which is the `infrahub-sdk-python`
submodule. Work on the SDK branch named after this Infrahub branch's base (`infrahub-develop` for
Infrahub `develop`), not the SDK's own `develop`.

**Independent Test**: Fetch a node with a declared attribute through the SDK and assert the returned
value's type; run a protocol-generation test asserting the emitted annotation.

### Tests for User Story 3

- [X] T026 [P] [US3] Write the value-coercion tests in `python_sdk/tests/unit/sdk/test_node.py` (or a
  focused new module beside it): a declared attribute's `.value` is `IPv4Address` / `IPv6Address`; an
  undeclared `IPHost` attribute's `.value` is still `IPv4Interface` / `IPv6Interface`; and a schema
  payload with **no** `allow_prefix` key yields today's behaviour (the old-server tolerance case).
- [X] T027 [P] [US3] Extend `python_sdk/tests/unit/sdk/test_protocols_generator.py`: a declared
  attribute renders `IPAddress`, a declared optional attribute with no default renders
  `IPAddressOptional`, and undeclared attributes still render `IPHost` / `IPHostOptional`.

### Implementation for User Story 3

- [X] T028 [US3] Make value coercion parameter-aware in
  `python_sdk/infrahub_sdk/node/attribute.py:111-118`: for `IPHost`, select `ipaddress.ip_address`
  when `allow_prefix` is `False` and `ipaddress.ip_interface` otherwise, reading the flag tolerantly as
  `(self._schema.parameters or {}).get("allow_prefix", True)` because
  `AttributeSchemaAPI.parameters` is `dict[str, Any] | None`
  (`python_sdk/infrahub_sdk/schema/main.py:149`). **Remove the now-unreachable `"IPAddress"` kind key**
  — no such attribute kind exists server-side; this is the dead-path cleanup the PRD called for, and
  the `ip_address` callable it referenced becomes the declared-`IPHost` branch.
- [X] T029 [US3] Make `_jinja2_filter_render_attribute` parameter-aware in
  `python_sdk/infrahub_sdk/protocols_generator/generator.py:117-124`: emit `IPAddress` /
  `IPAddressOptional` for a declared `IPHost` attribute, `IPHost` / `IPHostOptional` otherwise,
  composing with the existing `optional and default_value is None` suffix rule. No change is needed to
  `protocols_generator/constants.py`, `protocols_base.py`, or `template.j2` — all four protocol names
  are already registered and imported.
- [X] T030 [US3] Regenerate the SDK's `python_sdk/infrahub_sdk/protocols.py` and
  `python_sdk/infrahub_sdk/schema/generated/read.py` (the latter gains
  `IPHostAttributeParametersRead`) and run `cd python_sdk && uv run invoke format lint-code`
  (depends on T009, T028, T029).
- [X] T031 [US3] Add the SDK version floor to the SDK's own user-facing documentation: consuming a
  bare-address attribute requires an SDK at or above this version, because an older SDK silently
  re-attaches the host mask (see `contracts/sdk-contract.md` § Version skew).
- [ ] T032 [US3] **GATE — the SDK commit must be pushed.** Push the SDK branch to
  `origin` in `infrahub-sdk-python` and open the SDK pull request against `infrahub-develop`. The
  pointer bump in T033 requires the commit to be **fetchable from the remote**, which a pushed PR
  branch satisfies — root `AGENTS.md` § Submodules permits "merged *or the commit is otherwise
  available upstream*". Merge is **not** a prerequisite here; the only hard rule is that a pointer to
  an unpushed commit breaks every other checkout.
- [ ] T033 [US3] Bump the `python_sdk` submodule pointer to the latest pushed commit on the SDK PR
  branch (depends on T032). This lets Infrahub CI run against the real SDK change and unblocks review
  of both PRs in parallel, rather than serialising them behind the SDK merge. **This pointer is
  provisional** — see T045, which must run before the Infrahub PR merges.

**Checkpoint**: US1 and US3 both work. The feature is shippable end to end for API and SDK consumers.

### Phase 4 implementation notes (T026-T031)

- **SDK branch `infp-551-bare-ip-attribute`, commit `89e406a`** — created off the detached submodule
  HEAD `973eaa9`, which was verified an ancestor of `origin/infrahub-develop`
  (`git merge-base --is-ancestor`). **Not pushed.**
- **T032 and T033 were excluded from this run.** The SDK branch is local only, and the `python_sdk`
  pointer in this repo was deliberately left untouched. A human still needs to push the SDK branch,
  open the SDK PR, and then bump the pointer — in that order.
- **T028's dead-path removal confirmed dead before removing it.** The SDK's generated `AttributeKind`
  enum (`infrahub_sdk/schema/generated/enums.py`, generated from the backend's own enum) has no
  `IPADDRESS` member, and the backend schema reference lists no `IPAddress` accepted value. The two
  tests that exercised the kind were `@pytest.mark.skip`-ed for exactly that reason and were
  repurposed onto declared `IPHost` instead of deleted. The dead `"IPAddress": "IPAddress"` entry in
  `protocols_generator/constants.py` was left in place per T029, and is now genuinely reachable in
  spirit — the branch emits that protocol name — though not through a kind lookup.
- **T030's generated diff is confined to the four expected shapes**: the `parameters` union gained
  `IPHostAttributeParameters{Read,Write}`, an `IPHostAttribute{Read,Write}` discriminated member
  appeared, `AttributeKind.IPHOST` left the generic variant, and `invoke format` rewrapped the two
  now-longer union expressions. `infrahub_sdk/protocols.py` is **unchanged** — no attribute in the
  core schema declares the flag, so the protocol emission has nothing to change yet.
- **T031's version floor is SDK 1.23.0 against Infrahub 1.11.** Derived from the latest SDK tag
  (`v1.22.2`, so the next feature release is `1.23.0`) and the latest Infrahub tags (`1.11.0a*` in
  flight). It landed in the SDK's compatibility matrix — but that page is **generated**, so the edits
  are in `docs/docs_generation/compatibility.py` (`FEATURE_REQUIREMENTS`) and
  `docs/_templates/sdk_compatibility.j2` (the explanatory subsection and the silent-mask warning),
  with `docs/docs/python-sdk/reference/compatibility.mdx` regenerated. A first attempt at editing the
  `.mdx` directly was silently reverted by `invoke docs-generate`.
- **The unreleased changelog fragment `+ipaddress-attribute-kind.added.md` announced the kind being
  removed here**, so it was replaced by `+bare-iphost-attribute.added.md` describing the real
  behaviour. Leaving it would have shipped release notes for an attribute kind that does not exist.
- **Pre-existing SDK unit failures, unrelated and unchanged**: `test_repository_app` (2),
  `test_task_app::test_task_list_command`, `test_config::test_missing_password`, and a collection
  error in `test_cli::test_anonymous_info_detail_command_success`. Identical set before and after.

---

## Phase 5: User Story 2 — Operate on it in the UI (Priority: P2 — ships after P1)

**Goal**: An operator edits and views a bare-address attribute without ever meeting a prefix control
or a mask.

**Scope note — read before starting.** Research R6 established that **no frontend source change is
required**. `IP_HOST` appears nowhere in the form-field dispatch, table cell, or filter input; an
`IPHost` attribute falls through to `basicFormFieldProps` (a plain text input) at
`frontend/app/src/shared/components/form/utils/getFormFieldFromAttribute.ts:196`, and `prefixlen`
appears nowhere in `frontend/app/src` outside generated types. So FR-010 is already satisfied and the
UI half of FR-005 follows from bare storage. **This story's deliverable is a requirement guard, not a
component.** Do not build a dedicated IPHost input — that is out of scope.

**Independent Test**: Point the UI at a node whose schema has a declared attribute and exercise the
edit form, detail view, and list view.

- [ ] T034 [P] [US2] Add the FR-010 regression test to
  `frontend/app/src/shared/components/form/utils/getFormFieldFromAttribute.test.ts`: an `IPHost`
  attribute's form field carries **no** prefix-length control, with and without
  `parameters.allow_prefix`. This is the sole guard preventing a future dedicated IPHost input from
  violating FR-010 silently — treat it as a requirement test, not optional polish.
- [ ] T035 [US2] Add the E2E scenario under `frontend/app/tests/e2e/`: an operator creates a node
  whose bare-address attribute is entered as `10.0.0.1/32`, then sees `10.0.0.1` in the list view, the
  detail view, and the display label, with no prefix control anywhere in the form. Also assert an
  undeclared `IPHost` attribute still shows its mask (depends on T017, T018).
- [ ] T036 [US2] Confirm no frontend source change was required. If any turned out to be necessary,
  stop and record why in `plan.md` — it contradicts research R6 and means the scope assessment was
  wrong.

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T037 [P] Add the computed-attribute and template coverage to
  `backend/tests/integration_docker/test_computed_attributes.py`: a computed attribute referencing a
  declared attribute receives the **bare** value, and a display-label Jinja2 template referencing it
  renders with no mask. Constitution Principle IV requires Integration Docker coverage for
  computed-attribute features, which is why this is not a component test (critique E2).
- [ ] T038 [P] Write the user-facing documentation under `docs/` covering: how to declare a
  bare-address attribute; the immutability restriction and that in-place conversion is the tracked
  follow-up; **a manual conversion recipe for an existing populated `IPHost` attribute** (add a new
  bare-address attribute alongside, backfill through the SDK, repoint `display_labels` /
  `human_friendly_id` / uniqueness constraints, remove the old attribute); that authors should set the
  attribute's `description`, since the UI surfaces it as the only pre-submit hint that a prefix is
  disallowed; and the SDK version floor.
- [ ] T039 [P] Verify the attribute-kinds reference documentation renders `allow_prefix` correctly
  from the T003 field `description`; if the wording reads poorly, fix the `description` in
  `backend/infrahub/core/schema/attribute_parameters.py` and re-run `uv run invoke docs.generate`
  rather than editing the generated page.
- [ ] T040 [P] Add the Towncrier changelog fragment under `changelog/` per
  `dev/guidelines/` conventions, referencing INFP-551.
- [ ] T041 Update `dev/knowledge/backend/` with the load-bearing findings that outlive this feature:
  per-kind attribute parameters are the sanctioned extension point for kind-specific schema options;
  the schema-diff walker honours a parameter sub-field's own `update` classification
  (`backend/infrahub/core/models.py:279-300`); and derived IP properties are computed from the stored
  value, so bare storage keeps `prefixlen` truthful. Constitution requires backend architecture
  changes to update this directory.
- [ ] T042 Run the full local CI gate — `/pre-ci`, plus
  `cd frontend/app && pnpm exec biome ci . && pnpm knip && pnpm exec betterer ci && pnpm test`.
  Do **not** commit `.betterer.results` if the only change is `node_modules` path drift.
- [ ] T043 Walk every scenario in [quickstart.md](./quickstart.md) end to end, including the manual
  GraphQL smoke check. Note the local `infrahub upgrade` Prefect parameter-size workaround
  (`PREFECT_SERVER_API_MAX_PARAMETER_SIZE=0`) if testing the upgrade path.
- [ ] T044 Restate the Principle III deviation in the pull request description: the serialised form of
  an `IPHost` value becomes conditional on a schema parameter, the rejected simpler alternative was a
  separate `IPAddress` attribute kind, and the four narrowing mitigations from `plan.md` §
  Complexity Tracking. Constitution Governance requires any Principle VII/III deviation to be
  documented in the plan **or** PR; the plan has it, and the PR must too.
- [ ] T045 **PRE-MERGE GATE for the Infrahub PR.** Once the SDK PR has merged, re-point the
  `python_sdk` submodule from the provisional PR-branch commit (T033) to the merged commit, pinning
  `origin/infrahub-develop`. Then confirm the pointed-to commit is reachable from that branch —
  `cd python_sdk && git merge-base --is-ancestor HEAD origin/infrahub-develop`.

  **Why this is a separate gate rather than part of T033.** A provisional pointer is safe for CI and
  review but not for merge: if the SDK PR is squashed or rebased on merge, the PR-branch commit is no
  longer an ancestor of `infrahub-develop`, and deleting the SDK branch can leave it unreferenced and
  eventually unfetchable. An Infrahub commit on `develop` pointing at an orphaned SDK commit breaks
  every fresh clone — the exact failure the submodule rule exists to prevent. Blocking the *pointer*
  on the SDK merge is unnecessary; blocking the *Infrahub merge* on it is not.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; T001 must run on the **unmodified** tree to be meaningful.
- **Foundational (Phase 2)**: depends on Setup. **Blocks all three user stories** — the parameter must
  exist and be published before any story can read it.
- **US1 (Phase 3)**: depends on Phase 2. Delivers the MVP alone.
- **US3 (Phase 4)**: depends on Phase 2 for the schema contract and on T009 for the regenerated
  artefacts. Its tests can be written in parallel with US1, but T030's regeneration needs T009, and
  T033 is gated behind T032 — on the SDK commit being **pushed**, not merged.
- **US2 (Phase 5)**: T034 depends only on Phase 2; T035 (E2E) depends on US1's T017-T018, since the
  backend must actually store bare values for the E2E assertions to hold.
- **Polish (Phase 6)**: T037 depends on US1; T038-T044 depend on the stories they document or gate.
  T045 is gated on the **SDK PR merging** and must complete before the Infrahub PR merges.

### Critical Path

```text
T001 → T003 → T005 → T007 → T008 → T009 → T017 → T018 → T023 → T025 → T042 → T043
                                              ↓
                              T028/T029 → T030 → T032 (SDK push) → T033 (provisional pointer)
                                                                        ↓
                                              [SDK PR merges] → T045 (final pointer) → Infrahub merge
```

Nothing on the critical path waits on the SDK **merge**. T032 needs only a push, so both PRs can be
reviewed concurrently. The SDK merge is an external dependency of T045 alone, which sits immediately
before the Infrahub PR merges — so external review latency does not block development or CI.

### Within Each User Story

- Tests before implementation (T012-T016 before T017-T018; T026-T027 before T028-T029).
- Schema types (Phase 2) before behaviour (T017-T018) before regeneration (T023).
- T017 before T019, because the schema-load default rejection is a consequence of T017.

### Parallel Opportunities

- T002 runs alongside T001.
- T003, then T004/T005/T006 in sequence on the same two files; T010 in parallel once types exist.
- T012, T013, T014, T015, T016 are all `[P]` — five different test files or independent test
  functions.
- T026 and T027 are `[P]` and can proceed while US1 implementation is under way.
- T034 is `[P]` and independent of everything except Phase 2.
- T037, T038, T039, T040 are all `[P]`.
- **Cross-story**: once Phase 2 completes, a second engineer can take Phase 4 (SDK) while the first
  takes Phase 3 (backend). The SDK repo boundary makes this genuinely conflict-free.

---

## Parallel Example: User Story 1 tests

```bash
# Launch the five independent US1 test-writing tasks together:
Task: "T012 validation/normalisation matrix in backend/tests/component/core/test_attribute_iphost_allow_prefix.py"
Task: "T013 storage + derived-property assertions in the same file"
Task: "T014 HFID round trip in backend/tests/component/graphql/queries/test_hfid.py"
Task: "T015 uniqueness collision in test_attribute_iphost_allow_prefix.py"
Task: "T016 toggle rejection in backend/tests/integration/schema_lifecycle/test_attribute_parameters_update.py"
```

T012, T013, and T015 share one file — either assign them to one engineer sequentially or split into
separate test functions written independently and merged.

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 — Setup (baseline + fixture).
2. Phase 2 — Foundational (the declaration exists and is published). **Blocks everything.**
3. Phase 3 — US1.
4. **STOP and VALIDATE**: an author can declare a bare-address attribute and every backend read
   surface returns no mask. Verify T024's baseline match before going further.

At this point the feature is demonstrable and the migration-free property is proven.

### Incremental Delivery

1. Setup + Foundational → the declaration exists.
2. US1 → backend complete → **MVP, demo-able**.
3. US3 → SDK consumers get the right type → ships with US1 per the spec, gated on the upstream merge.
4. US2 → UI verified → the regression guard is in place.
5. Polish → computed-attribute coverage, documentation, changelog, CI gate.

### Definition of Done

- All 45 tasks complete.
- T024's baseline comparison is clean — zero existing IPHost tests modified.
- `uv run invoke docs.validate` clean; no stale generated files.
- The submodule pointer never referenced an unpushed commit (T032 before T033), and by merge time it
  references a commit that is an ancestor of `origin/infrahub-develop` (T045).
- The Principle III deviation is restated in the PR (T044).

---

## Notes

- `[P]` = different files, no dependencies on incomplete tasks.
- The 🎯 Must-Address items from the critique are already folded in: T007 + T010 + T019 (default-value
  handling, E1), T037 (computed attributes, E2), and the corrected SC-001/SC-004 baselines in `spec.md`
  (P2).
- Three requirements need **no implementation task**, only verification, because research proved them
  already satisfied: FR-002 (`extra="forbid"`, verified by T010), FR-009 (the diff walker already
  emits `parameters.allow_prefix`, verified by T016), FR-013 (`parameters` is already published at
  `WRITE` visibility, verified by T023). Do not add code for these.
- FR-008 likewise needs no code — `to_db()` is untouched. T013 exists to keep it that way.
