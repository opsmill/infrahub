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

- [ ] T003 Add `IPHostAttributeParameters(AttributeParameters)` with
  `allow_prefix: bool = Field(default=True, description=..., json_schema_extra={"update": UpdateSupport.NOT_SUPPORTED.value})`
  to `backend/infrahub/core/schema/attribute_parameters.py`. The `description` text becomes the
  attribute-kinds reference documentation, so write it for a schema author. Default `True` is what
  guarantees FR-012.
- [ ] T004 Register `"IPHost": IPHostAttributeParameters` in
  `get_attribute_parameters_class_for_kind` in
  `backend/infrahub/core/schema/attribute_parameters.py` (depends on T003).
- [ ] T005 Add `IPHostAttributeSchema(AttributeSchema)` carrying the typed
  `parameters: IPHostAttributeParameters` field (mirroring `TextAttributeSchema`) and register
  `"IPHost": IPHostAttributeSchema` in `attribute_schema_class_by_kind`, both in
  `backend/infrahub/core/schema/attribute_schema.py` (depends on T003).
  **Registration is load-bearing**: `backend/infrahub/core/schema/basenode_schema.py:152-174` upgrades
  every attribute to its per-kind class, which is what makes `parameters.allow_prefix` reachable from
  the attribute class.
- [ ] T006 Add the reverse guard to `AttributeSchema.validate_parameters` in
  `backend/infrahub/core/schema/attribute_schema.py` — an `IPHostAttributeParameters` instance on a
  non-`IPHost` kind raises `"IPHostAttributeParameters can't be used as parameters for {kind}"`,
  matching the three existing branches at lines 157-166 (depends on T003).
- [ ] T007 Add a model validator to `IPHostAttributeSchema` in
  `backend/infrahub/core/schema/attribute_schema.py` that strips a redundant host mask from
  `default_value` when `allow_prefix` is `False`, so the schema records `10.0.0.1` rather than
  `10.0.0.1/32` (depends on T005). Without this the schema advertises a default that no node ever
  receives — see critique E1.
- [ ] T008 Add `IPHostAttributeParameters` to the `internal_kind` list of the `parameters`
  `SchemaAttribute` at `backend/infrahub/core/schema/definitions/internal.py:803-817` (depends on
  T003). This is the single edit that produces the core-schema diff.
- [ ] T009 Regenerate backend artefacts — `uv run invoke backend.generate` — and commit the resulting
  changes to `backend/infrahub/core/schema/generated/` and `backend/infrahub/core/protocols.py`
  (depends on T008). **Verify the diff is confined to the `parameters` type union**; anything wider
  means a mistake in T003-T008.
- [ ] T010 [P] Write the schema-type unit tests in
  `backend/tests/unit/core/schema/test_iphost_attribute_parameters.py`: `allow_prefix` defaults to
  `True`; `allow_prefix` on a `Text` attribute is rejected by `extra="forbid"`;
  `IPHostAttributeParameters` on a non-`IPHost` kind raises; the field carries
  `UpdateSupport.NOT_SUPPORTED`; a `/32` `default_value` is normalised to bare and a bare one is left
  alone; an undeclared attribute's `default_value` is untouched (depends on T003-T007).
- [ ] T011 Confirm the baseline still holds — re-run the T001 command and diff against
  `/tmp/iphost-baseline.txt`. Schema types alone must change no behaviour.

**Checkpoint**: The declaration exists, is guarded on other kinds, is immutable by classification, and
is published in the schema contract. All three stories can now proceed.

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

- [ ] T012 [P] [US1] Write the validation and normalisation matrix in
  `backend/tests/component/core/test_attribute_iphost_allow_prefix.py`: {bare, `/32`, `/128`, `/24`,
  `/64`, `/31`, `/0`} × {IPv4, IPv6} × {declared, undeclared}. Declared rejects every non-host prefix
  with an error naming the attribute; declared stores bare for bare and host-mask input; undeclared
  behaves exactly as today. Include the optional-attribute null path (no prefix logic applied).
- [ ] T013 [P] [US1] Write the storage and derived-property assertions in the same file: for a
  declared attribute the stored `value` is bare **and** the value vertex still carries
  `prefixlen == 32` (IPv4) / `128` (IPv6), `binary_address`, and `version`; an IPAM prefix-containment
  query for `10.0.0.0/8` still returns the node. This test guards FR-008 against a future "clean up
  the meaningless prefixlen" refactor.
- [ ] T014 [P] [US1] Extend `backend/tests/component/graphql/queries/test_hfid.py` with a
  bare-address counterpart to the existing `test_iphost_hfid_roundtrip_via_graphql` (the #8896
  reproduction): the HFID and display label carry no mask, and the HFID returned by a query is
  accepted verbatim as lookup input with zero caller-side transformation.
- [ ] T015 [P] [US1] Write the uniqueness collision test in
  `backend/tests/component/core/test_attribute_iphost_allow_prefix.py`: on a declared attribute with a
  uniqueness constraint, nodes created with `10.0.0.1` and `10.0.0.1/32` collide. Assert the same two
  inputs also collide on an undeclared attribute (both store `10.0.0.1/32`), so the test distinguishes
  the new behaviour from the old.
- [ ] T016 [P] [US1] Extend
  `backend/tests/integration/schema_lifecycle/test_attribute_parameters_update.py` with the toggle
  rejection (FR-009): flipping, adding, or removing `allow_prefix` on an existing attribute fails with
  an unsupported-change error naming `parameters.allow_prefix`.

### Implementation for User Story 1

- [ ] T017 [US1] Make `IPHost.validate_format` parameter-aware in
  `backend/infrahub/core/attribute.py:1130-1148`: after the existing `ip_interface(value)` check, when
  the schema declares `allow_prefix=False` and the parsed interface's `network.prefixlen` is not the
  host length for its version (32 / 128), raise `ValidationError` keyed by the attribute `name` with a
  message stating a subnet prefix is not permitted. Read the flag as
  `getattr(schema.parameters, "allow_prefix", True)` — the method is typed against the base
  `AttributeSchema` and inherited/profile/template paths may pass a base-classed instance.
  **Check the parsed prefix length, never the presence of `/` in the string**, or `/32` would be
  wrongly refused.
- [ ] T018 [US1] Make `IPHost._normalize_value` parameter-aware in
  `backend/infrahub/core/attribute.py:1150-1151`: return `str(ipaddress.ip_interface(value).ip)` when
  the flag is off, else keep `ipaddress.ip_interface(value).with_prefixlen` exactly as today. Read the
  flag from `self.schema.parameters` (set at `attribute.py:120`, before the validate/normalise pair
  runs at `attribute.py:166-167`). Leave `to_db()` and every derived property untouched.
- [ ] T019 [US1] Add the schema-load default-value tests to
  `backend/tests/component/core/schema_manager/test_manager_schema.py`: a declared attribute with
  `default_value: "10.0.0.1/24"` fails to load with a `default value ...` error naming the attribute
  (this falls out of T017 via `SchemaBranch.validate_default_values()` at
  `backend/infrahub/core/schema/schema_branch.py:1048-1066`), a `/32` default loads and is recorded
  bare, and a node created with no explicit value receives the bare default (depends on T007, T017).
- [ ] T020 [US1] Add the profile and template tests to
  `backend/tests/component/core/test_attribute_iphost_allow_prefix.py`: a profile node and a template
  node inheriting a declared attribute validate and serialise identically to the node they derive
  from. **This is the highest-value test in the set** — silent flag loss on these paths would look
  exactly like the feature working (plan Risks).
- [ ] T021 [US1] Add the branch-merge tests to the same file: an attribute declared on a branch
  carries both the declaration **and** its rejection behaviour to the target branch after merge; and
  two branches setting `10.0.0.1` and `10.0.0.1/32` on the same declared attribute produce **no**
  merge conflict, because they converge on one stored value. Required by Constitution Principle II.
- [ ] T022 [US1] Add the kind-change test to the same file, pinning today's behaviour: changing a
  declared attribute's kind away from `IPHost` silently drops `allow_prefix` (via
  `set_parameters_type` in `backend/infrahub/core/schema/attribute_schema.py:136-153`). The spec
  accepts this silence for v1; the test exists so a future change to it is deliberate.
- [ ] T023 [US1] Regenerate the remaining contract artefacts and commit them:
  `uv run invoke schema.generate-graphqlschema`, `uv run invoke schema.generate-jsonschema`,
  `uv run invoke docs.generate`, and `cd frontend/app && pnpm codegen` (depends on T009).
- [ ] T024 [US1] Verify the FR-012 gate: re-run the T001 command and confirm the results match
  `/tmp/iphost-baseline.txt` exactly. **Any modification needed to an existing IPHost test is a
  regression, not a test-maintenance task** — investigate rather than adjust the test.
- [ ] T025 [US1] Verify `uv run invoke docs.validate` is clean, so CI's
  `validate-generated-documentation` job will pass (depends on T023).

**Checkpoint**: US1 is fully functional and independently demonstrable. The MVP is complete — an author
can declare a bare-address attribute and every backend read surface returns no mask.

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

- [ ] T026 [P] [US3] Write the value-coercion tests in `python_sdk/tests/unit/sdk/test_node.py` (or a
  focused new module beside it): a declared attribute's `.value` is `IPv4Address` / `IPv6Address`; an
  undeclared `IPHost` attribute's `.value` is still `IPv4Interface` / `IPv6Interface`; and a schema
  payload with **no** `allow_prefix` key yields today's behaviour (the old-server tolerance case).
- [ ] T027 [P] [US3] Extend `python_sdk/tests/unit/sdk/test_protocols_generator.py`: a declared
  attribute renders `IPAddress`, a declared optional attribute with no default renders
  `IPAddressOptional`, and undeclared attributes still render `IPHost` / `IPHostOptional`.

### Implementation for User Story 3

- [ ] T028 [US3] Make value coercion parameter-aware in
  `python_sdk/infrahub_sdk/node/attribute.py:111-118`: for `IPHost`, select `ipaddress.ip_address`
  when `allow_prefix` is `False` and `ipaddress.ip_interface` otherwise, reading the flag tolerantly as
  `(self._schema.parameters or {}).get("allow_prefix", True)` because
  `AttributeSchemaAPI.parameters` is `dict[str, Any] | None`
  (`python_sdk/infrahub_sdk/schema/main.py:149`). **Remove the now-unreachable `"IPAddress"` kind key**
  — no such attribute kind exists server-side; this is the dead-path cleanup the PRD called for, and
  the `ip_address` callable it referenced becomes the declared-`IPHost` branch.
- [ ] T029 [US3] Make `_jinja2_filter_render_attribute` parameter-aware in
  `python_sdk/infrahub_sdk/protocols_generator/generator.py:117-124`: emit `IPAddress` /
  `IPAddressOptional` for a declared `IPHost` attribute, `IPHost` / `IPHostOptional` otherwise,
  composing with the existing `optional and default_value is None` suffix rule. No change is needed to
  `protocols_generator/constants.py`, `protocols_base.py`, or `template.j2` — all four protocol names
  are already registered and imported.
- [ ] T030 [US3] Regenerate the SDK's `python_sdk/infrahub_sdk/protocols.py` and
  `python_sdk/infrahub_sdk/schema/generated/read.py` (the latter gains
  `IPHostAttributeParametersRead`) and run `cd python_sdk && uv run invoke format lint-code`
  (depends on T009, T028, T029).
- [ ] T031 [US3] Add the SDK version floor to the SDK's own user-facing documentation: consuming a
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
