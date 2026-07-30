# PR split plan — bare IP addresses on IPHost attributes

Plan for restructuring the work on `bare-ip-attribute-infp-551` into a feature branch plus a stack of
reviewable pull requests. The feature branch, PR 1 and the SDK pull request are built; PRs 2–5 are not.
See Execution state immediately below for what is current.

## Execution state

**Read this first — the strategy below was written before the stack was built, and PRs 1 and the SDK
change have since landed. Where this section and the strategy sections disagree, this section is
current.**

| Item | State |
|---|---|
| Feature branch `infp-551-bare-ip-attribute` | **pushed**, off `origin/release-1.11`; spec documents only, all 46 tasks unchecked |
| PR 1 branch `infp-551-01-declaration` | **pushed** — 8 commits, tip `6037b36e5` |
| PR 1 | **open as draft: opsmill/infrahub#10081** → feature branch |
| SDK branch `infp-551-bare-ip-attribute` (in `infrahub-sdk-python`) | **pushed** — 4 commits, tip `525b28f` |
| SDK PR | **open as draft: opsmill/infrahub-sdk-python#1220** → `infrahub-develop` |
| Reference branch `bare-ip-attribute-infp-551` | **unmodified reference copy** of the full verified work. Do not rewrite or delete it — the faithfulness check depends on it. |
| Superseded PR | opsmill/infrahub#10066 — the original single PR. Still open; carries the Principle III write-up and seven cubic review threads. No umbrella PR exists yet to inherit them. |
| PRs 2–5 | **not built** |

**Submodule pointer.** PR 1 and the reference branch both pin **`525b28f`** — not the `89e406a` cited in
the strategy sections below, which was superseded when the SDK took two further commits. `release-1.11`
and the feature branch still pin `681b458c`. **PRs 2–5 inherit `525b28f` from PR 1 and must not change
it.**

**Branch naming.** `infp-551-<NN>-<slug>`: `infp-551-01-declaration` exists; PR 2 is
`infp-551-02-write-behaviour`, then `-03-lookup`, `-04-verification`, `-05-docs`. Each is based on its
predecessor, not on the feature branch.

**Three commits landed after this plan was written**, all already in PR 1:

| Commit | Content | Slice |
|---|---|---|
| `43b9e45ef` | reject prefixed defaults, typed fixture, `DNS_RECORD_DEFINITION` → `DNS_RECORD_DICT` | **1 and 2** — see "The review commit spans two slices" |
| `a109b32bd` | reworded `allow_prefix` description across 5 files + pointer bump to `525b28f` | 1 only |
| `c56f08b92` | stopped re-exporting `DNS_RECORD_DICT` from `helpers/schema/__init__.py`; condensed a generator comment | 1 only |

A builder cherry-picking PR 2 by the commit lists below must **not** replay `a109b32bd` or `c56f08b92` —
they are PR 1's, already merged into its history.

**Tests.** PR 1 was built and verified structurally, with no test runs, because it contains no
behaviour. **PR 2 is different**: five commits and roughly 1300 lines of behavioural tests, where
structural checks prove almost nothing. It warrants a real run. Confirm with the author before starting,
since the earlier PRs were explicitly built without one.

## Shape

```text
release-1.11
  └── infp-551-bare-ip-attribute            ← feature branch: spec documents only, all tasks unchecked
        └── infp-551-01-declaration         ← PR 1  declaration + published contract   [#10081, draft]
              └── infp-551-02-write-behaviour   ← PR 2  write behaviour (bare storage)
                    └── infp-551-03-lookup          ← PR 3  lookup normalisation
                          └── infp-551-04-verification  ← PR 4  frontend, E2E, integration_docker
                                └── infp-551-05-docs        ← PR 5  documentation, changelog, knowledge
```

The feature branch targets **`release-1.11`**, not `develop`. This aligns with the version floor the
feature already documents (SDK 1.23.0 / Infrahub 1.11) — the docs page and the SDK compatibility matrix
both name 1.11 as the first release carrying bare-address attributes, so shipping through the release
branch makes the documented claim true rather than aspirational.

### Rebase assessment onto `release-1.11` — verified

| Check | Result |
|-------|--------|
| Current fork point `62bd11b59` an ancestor of `release-1.11`? | **Yes** — no history rewrite needed to reparent |
| `develop` commits absent from `release-1.11` | 6 |
| `release-1.11` commits absent from `develop` | 3 |
| File overlap between release-only commits and this feature's 35 changed files | **None** |

The release-only commits touch `pyproject.toml` (breaking apart ty ignore rules),
`core/merge/selective_regen/generator_diff_capturer.py`, and its test. No collision with anything this
feature changes, so the rebase should be mechanical.

One thing to re-verify after rebasing: `c95da07a9` restructures the ty ignore rules in `pyproject.toml`,
and PR 1's `tasks/backend.py` formatting fix sits adjacent to that concern (it supersedes a pre-existing
`E501` per-file-ignore). Re-run `uv run invoke backend.lint` and `uv run invoke backend.validate-generated`
after the rebase rather than assuming the pre-rebase results carry over.

Five PRs, **stacked** — each based on the previous, not on the feature branch directly. Stacking is what
makes each PR's CI meaningful: a PR based on the feature branch alone would be missing its
prerequisites and go red for reasons unrelated to its own content. Merge strictly in order 1 → 5.

| PR | Hand-written lines | Generated lines | Files | Review question |
|----|-------|-----------|-------|-----------------|
| 1 | 257 | 1205 | 14 | Is the declaration modelled correctly and published everywhere? |
| 2 | 1316 | 0 | 5 | Is the write behaviour right, and is the undeclared path genuinely untouched? |
| 3 | 648 | 0 | 8 | Does the masked spelling resolve as lookup input, on every path? |
| 4 | 331 | 0 | 5 | Do the surfaces we cannot unit-test actually work? |
| 5 | 340 | 0 | 6 | Is the documentation correct and honest about limitations? |

## Feature branch preparation

Branch `infp-551-bare-ip-attribute` off `origin/release-1.11`, containing **only** `dev/specs/infp-551-bare-ip-attribute/`:

- `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`, `checklists/`,
  `critiques/`, `alignment-check.md`, `opsmill-implement-report.md`, and this file.
- Take the **corrected** state of every document — i.e. include the fixes from `f6d1c0486` (the
  Rejection-cases table in `contracts/schema-contract.md`, FR-002 in `spec.md`, `data-model.md`) and
  `a7e07b682` (stale commands and the deprecated `display_labels` field in `quickstart.md`). Those
  corrections are real and should not be re-litigated per PR.
- `tasks.md` with **every checkbox reset to `[ ]`**, including `T046` (added mid-flight) and keeping the
  `[~]` on `T032` reset to `[ ]`.
- Keep the "Phase N implementation notes" and "Review findings addressed" subsections in `tasks.md`.
  They are the provenance for decisions that deviated from the original task text, and reviewers of the
  child PRs will want them.

No code on the feature branch. Every code change arrives through a PR.

## Hard coupling constraints

These determine the seams. Each one is a case where splitting commits apart produces a PR with red CI,
so they are not stylistic preferences.

**C1 — The submodule pointer bump requires the generator formatting fix.**
`uv run invoke backend.generate` emits the SDK's `AttributeSchemaRead` / `AttributeSchemaWrite` union as
one unwrapped line; the committed SDK file is ruff-wrapped. Below 120 characters the two agree. Adding
`IPHostAttributeWrite` pushes the line past the limit, so `backend-validate-generated` sees a
formatting-only diff and fails. `41e994961` (a third `ruff format` pass so formatting runs last) must be
present at or before `e72373922`. → same PR.

**C2 — The submodule pointer bump is a functional prerequisite for the integration tests.**
`SchemaLoadAPI` inherits the SDK's *generated* write models. Without `IPHostAttributeWrite`, an `IPHost`
attribute matches `GenericAttributeWrite`, whose `parameters` is field-less with `extra="ignore"` — so
`allow_prefix` is **silently dropped from every `/api/schema/load` payload**. Verified empirically:
`TestAllowPrefixIsImmutable` fails 4 of its cases at the old pointer, and passes at any SDK commit carrying `IPHostAttributeWrite` (`89e406a` originally, `525b28f` now). → any PR
containing a test that loads a declared attribute through the API must land at or after the bump.

**C3 — Regenerating the REST types requires the frontend mirror fix.**
`8428be5f2` adds `IPHostAttributeRead` to the attribute discriminated union in
`frontend/app/src/shared/api/rest/types.generated.ts`. `src/entities/schema/domain/model/schema.ts`
hand-mirrors that union and, without the new member, produces 46 new TypeScript errors and fails
`betterer ci` (`got worse. (46 new issues, 190 existing, 236)`). → `8428be5f2` and `8cc76e705` same PR.

**C4 — The TDD pairs cannot be separated.**
`c6a6db5c2` deliberately lands 15 failing tests, which `c59066c42` turns green. Likewise `4f5ab9068`
carries both the update-path fix and the tests that fail without it. Splitting a test commit from its
implementation produces a PR that is red by construction. → each test/implementation pair stays together.

**C5 — The schema-type unit tests depend on the shared fixture.**
`backend/tests/unit/core/schema/test_iphost_attribute_parameters.py:19` imports
`DNS_RECORD_DEFINITION` from `backend/tests/helpers/schema/dns_record.py`. → `fcb27f3d3` (the fixture)
must ship in PR 1 with the unit tests, not later with the behavioural tests.

**C6 — The docs page and changelog fragment are created late and edited earlier in the new order.**
`docs/docs/schema/ip-address-attributes.mdx` and `changelog/+infp-551-bare-iphost-attribute.added.md`
are **created** in `eb3c612f4` but **edited** in `08b4e677a`, which the new ordering places in an earlier
PR. Resolution: strip all documentation and changelog hunks out of the code PRs and consolidate them
into PR 5, which lands the final content in one place. This is better for review anyway — one PR to read
the user-facing wording — at the cost of the changelog fragment not travelling with the feature commit.
See Open decisions.

**C7 — One commit supersedes part of another and should not be reviewed twice.**
`08b4e677a` introduced `_normalize_hfid` with hand-rolled `str.partition("__")` parsing; `221568c60`
replaced that with `parse_schema_path()`. Reviewers should not read the hand-roll and then its
replacement. → squash the two, or rewrite `08b4e677a`'s `manager.py` hunk to use `parse_schema_path`
from the outset so the intermediate approach never appears in the history.

## The pull requests

### PR 1 — Declare `allow_prefix` and publish it through every contract

**Commits**: `fcb27f3d3`, `a30cfd1fc`, `41e994961`, `e72373922`, `8428be5f2`, `8cc76e705`

**Files**: `core/schema/attribute_parameters.py`, `core/schema/attribute_schema.py`,
`core/schema/definitions/internal.py`, `core/schema/generated/attribute_schema.py`,
`backend/templates/attributeschema_imports.j2`, `tasks/backend.py`,
`tests/helpers/schema/{__init__,dns_record}.py`,
`tests/unit/core/schema/test_iphost_attribute_parameters.py`, `python_sdk` (pointer),
`schema/openapi.json`, `frontend/.../types.generated.ts`,
`frontend/.../entities/schema/domain/model/schema.ts`, `frontend/app/.betterer.results`

**Why these travel together**: C1, C3, C5. The pointer bump, the generator formatting fix, the
regenerated artefacts, and the frontend mirror form one atomic unit — any subset leaves CI red.

**What a reviewer checks**: is `allow_prefix` modelled in the right place (per-kind parameters rather
than on `AttributeSchema`), is it correctly classified `NOT_SUPPORTED`, is the reverse guard right, does
the `default_value` normalisation belong here, and is the generated diff confined to the `parameters`
type union.

**Deliberately contains no behaviour change.** Nothing about how a value is stored or returned changes in
this PR — that makes it a genuinely cheap review despite the 1205 generated lines, which reviewers can
skim once they have checked the four hand-written schema files.

**CI**: green. The 14 unit tests exercise schema types only.

**External dependency**: bumps the submodule pointer, so the SDK PR must be open and pushed before this
merges, and `T045` (re-pin to the merged SDK commit, confirm it is an ancestor of
`origin/infrahub-develop`) applies to *this* PR rather than to the stack as a whole.

### PR 2 — Store bare values on write

**Commits**: `c6a6db5c2`, `c59066c42`, `837105d00`, `4f5ab9068`, `b9bbbad04`

**Files**: `core/attribute.py`, `tests/component/core/test_attribute_iphost_allow_prefix.py`,
`tests/component/graphql/queries/test_hfid.py`,
`tests/component/core/schema_manager/test_manager_schema.py`,
`tests/integration/schema_lifecycle/test_attribute_parameters_update.py`

**Why these travel together**: C4 (two test/implementation pairs) and C2 (`b9bbbad04` is an integration
test through `/api/schema/load`, so it needs PR 1's pointer bump — satisfied by stacking).

**What a reviewer checks**: the version-agnostic host-length comparison (`interface.ip.max_prefixlen`,
never a hardcoded 32/128), that the flag is read consistently including on profile, template and
inherited paths, that `to_db()` and the derived properties are genuinely untouched, and — most
importantly — that every behavioural test pairs a declared attribute with an undeclared control
asserting the old behaviour.

**The largest PR at 1316 lines, but ~85% is test code.** The production change is roughly 40 lines in
`core/attribute.py`.

**Optional split point.** If this is still too large, the clean seam is create-path vs update-path:
PR 2a = `c6a6db5c2` + `c59066c42` + `837105d00` (create), PR 2b = `4f5ab9068` + `b9bbbad04` (update).
Splitting has real merit — the update-path commit also closes a **uniqueness bypass** (the pre-save
uniqueness check ran against the un-normalised value, so `10.0.0.1/32` could be written alongside an
existing `10.0.0.1`), and that deserves a reviewer's undivided attention rather than being the fourth
commit in a large PR. Taking this option makes it a 6-PR stack.

**CI**: green.

#### Building PR 2 — the operational detail

Base on `infp-551-01-declaration`. Branch `infp-551-02-write-behaviour`. Cherry-pick `c6a6db5c2`,
`c59066c42`, `837105d00`, `4f5ab9068`, `b9bbbad04` in that order, dropping every `dev/specs/` hunk
(`git cherry-pick -n <sha>` then `git checkout HEAD -- dev/specs/`, then commit with the original
message).

**Then fold in `43b9e45ef`'s three PR-2 files** — they could not be applied at PR 1 because the files did
not exist there:

| File | What to apply |
|---|---|
| `tests/component/core/test_attribute_iphost_allow_prefix.py` | `DNS_RECORD_DEFINITION` → `DNS_RECORD_DICT` (import + use) |
| `tests/integration/schema_lifecycle/test_attribute_parameters_update.py` | same rename |
| `tests/component/core/schema_manager/test_manager_schema.py` | the rename **plus** the inverted default-value expectations |

Apply the commit's own diff rather than checking out its blobs — its blobs contain PR 3's additions and
would drag them in.

**Class ownership of the shared test file.** `test_attribute_iphost_allow_prefix.py` is the most
conflict-prone file in the split. PR 2's version must contain exactly these, and nothing else:

| Class | Introduced by | Slice |
|---|---|---|
| `ValueCase` | `c6a6db5c2` | 2 |
| `TestValueValidationAndNormalisation` | `c6a6db5c2` | 2 |
| `TestStorageAndDerivedProperties` | `c6a6db5c2` | 2 |
| `TestUniquenessAcrossInputForms` | `c6a6db5c2` | 2 |
| `TestGeneratedKindsInheritTheDeclaration` | `837105d00` | 2 |
| `TestBranchMerge` | `837105d00` | 2 |
| `TestAttributeKindChange` | `837105d00` | 2 |
| `TestTheUpdatePath` | `4f5ab9068` | 2 |
| `TestLookupInput` | `08b4e677a` | **3 — must be absent** |
| `DelegationRecords`, `HierarchyRecords`, `TestLookupInputReachedThroughARelationship` | `221568c60` | **3 — must be absent** |

Likewise `tests/unit/core/schema/test_iphost_attribute_parameters.py` carries **two** test classes at PR 2
(`TestAllowPrefixDeclaration`, `TestDefaultValuePrefixPolicy`); the third,
`TestQueryValueNormalisation`, is PR 3's and is already correctly absent from PR 1.

**Structural leak-checks — run all of these and report each result.** They are what makes the branch
verifiable:

1. `test_attribute_iphost_allow_prefix.py` contains the eight PR-2 classes above and **none** of the four
   PR-3 ones.
2. `backend/infrahub/core/manager.py` — **unchanged** vs `infp-551-01-declaration` (PR 3 owns it).
3. `backend/infrahub/core/query/node.py` — **unchanged** (PR 3).
4. `backend/infrahub/core/schema/attribute_schema.py` contains **no** `normalize_query_value` and **no**
   `_bare_host_address` (both PR 3).
5. `backend/tests/helpers/schema/dns_delegation.py` — **absent** (PR 3 creates it).
6. `backend/tests/unit/core/schema/test_iphost_attribute_parameters.py` contains no
   `TestQueryValueNormalisation`.
7. No file under `dev/specs/` differs from the base branch.
8. The submodule pointer is still `525b28f` — unchanged from PR 1.
9. No frontend file and no `integration_docker` file is touched (PRs 4).
10. `git diff bare-ip-attribute-infp-551 HEAD -- <each PR-2 path>` is empty except where PR 3's additions
    are legitimately absent — name every file that differs, and why.

**Lint status is unverified on the inherited commits.** `43b9e45ef` was committed without running
`format` or `lint`; PR 1 needed a `ruff format` reflow and a missing `Raises:` section (DOC501) on
`reject_prefixed_default_value` as a result. **Its three PR-2 files carry the same unverified status** —
run `uv run invoke format` and `uv run invoke lint` and expect to fix something. If `format` wants to
reflow a file you only cherry-picked, that is inherited debt, not a bad pick.

**Behavioural note the expectations depend on.** `43b9e45ef` moved the subnet-prefix `default_value`
rejection from `SchemaBranch.validate_default_values()` (an `infrahub.exceptions.ValidationError` naming
the schema kind) to Pydantic model validation (a `pydantic.ValidationError` naming only the attribute).
`test_manager_schema.py` therefore asserts `pytest.raises(PydanticValidationError, match=...)` **without
an anchor**, because Pydantic prepends its own preamble. That assertion has never been executed — treat it
as the most likely thing to need adjusting.

### PR 3 — Normalise lookup input

**Commits**: `08b4e677a`, `221568c60` — **squash or rewrite per C7**

**Files**: `core/manager.py`, `core/query/node.py`, `core/schema/attribute_schema.py`,
`tests/helpers/schema/dns_delegation.py`,
`tests/component/core/test_attribute_iphost_allow_prefix.py`,
`tests/unit/core/schema/test_iphost_attribute_parameters.py`

**Doc and changelog hunks from `08b4e677a` move to PR 5** per C6.

**What a reviewer checks**: that `normalize_query_value` is a no-op on the base class so `IPNetwork`,
`MacAddress` and undeclared `IPHost` are provably unaffected; that three seams is the right number and
they are the right three (`get_query_filter`, `NodeGetListQuery._build_attribute_filter_requirement`,
HFID resolution) rather than a shotgun; the decision that a subnet-prefix filter value matches nothing
and raises nothing; and the `AttributePathParsingError` catch-and-passthrough preserving the previous
graceful degradation on a read path.

**Why it is separable from PR 2**: writes and reads are independently correct. PR 2 makes storage bare;
PR 3 makes the non-canonical spelling resolve against it. A reviewer can accept PR 2 and reject PR 3's
approach without unpicking anything.

**CI**: green.

### PR 4 — Verification surfaces

**Commits**: `b9f119a9e`, `285072243`

**Files**: `frontend/.../getFormFieldFromAttribute.test.ts`,
`frontend/app/tests/e2e/objects/bare-address-attribute.spec.ts`,
`frontend/app/tests/e2e/utils/schema.ts`, `tests/integration_docker/test_computed_attributes.py`,
`tests/integration_docker/test_files/computed_tshirt.yml`

**Why this is its own PR — the strongest argument in the whole plan.** These are the only two tests in
the feature that were **never executed locally**: the Playwright E2E needs a full stack with a built
frontend, and the integration_docker test needs a testcontainers stack that will not boot in the
development environment (RabbitMQ `.erlang.cookie: eacces`, `task-manager` exits 127). This PR is
therefore the first place either test genuinely runs. Isolating them means a failure blocks **only this
PR** instead of blocking a PR that also carries production code. The four PRs of actual behaviour can
merge on verified evidence while these two are debugged against real CI.

**What a reviewer checks**: that the frontend test is a requirement guard rather than polish — and note
the known weakness recorded in the implement report, that it asserts a kind-level shape and would
survive a full revert; that the E2E loads its own schema because `models/base` has no `IPHost`
attribute; and that the integration_docker fixture's node indices are unchanged so index-addressed
existing tests are unaffected.

**CI**: **this is the PR expected to need iteration.** Treat red here as information, not regression.

### PR 5 — Documentation, changelog, and internal knowledge

**Commits**: `eb3c612f4`, plus the doc/changelog hunks lifted out of `08b4e677a` per C6

**Files**: `docs/docs/schema/ip-address-attributes.mdx`, `docs/docs/schema/nodes-and-attributes.mdx`,
`docs/sidebars.ts`, `dev/knowledge/backend/schema-definitions.md`,
`dev/knowledge/backend/database-schema.md`, `changelog/+infp-551-bare-iphost-attribute.added.md`

**What a reviewer checks**: the manual conversion recipe for an existing populated attribute — it is the
only workaround for the immutability restriction, so a vague recipe is worse than none. Note the recipe
documents a real trap found while writing it: `HashableModel.update` overwrites scalars with payload
defaults, so a partial schema payload silently flips `optional`, which is why every example shows the
complete node definition. Also check the page is honest about the limitations listed in the implement
report.

**Why last**: the documentation describes the finished behaviour, so it can only be reviewed accurately
once PRs 1–3 have settled. It is also the cheapest to review and the least likely to need rework, so it
is the right thing to have outstanding if the stack stalls.

**CI**: documentation jobs only.

## Review annotations, and which PR owns each

Eleven `TODO` annotations were added to the working tree during review of the assembled branch. They are
recorded here verbatim so the comments themselves do not have to ship inside a PR — `.agents/rules/code-doc-style.md`
asks for the *why* in comments, not intent-to-change, and a reviewer would rightly flag a TODO added by
the same PR that introduces the code. Ownership is assigned by which commit introduced the code being
annotated.

### Resolved before PR 1 ships

| Annotation | Location |
|---|---|
| "this looks more like it should raise an error. if a `default_value` with a prefix is included on a `parameters.allow_prefix=False` attribute, we should just prevent it" | `core/schema/attribute_schema.py`, `strip_redundant_host_mask_from_default` |
| "this does not follow our normal testing patterns. this should use pytest fixtures. ideally it would build the typed `SchemaNode` instead of using a dict" | `tests/helpers/schema/dns_record.py` |
| "this test does nothing" | `tests/unit/core/schema/test_iphost_attribute_parameters.py`, `test_allow_prefix_cannot_be_updated` |

Two of these change intent rather than style, so each carries a note:

- **Raise instead of strip** supersedes T007's original rationale (and critique E1), which chose silent
  normalisation so the schema would not advertise a default no node receives. Raising is defensible on a
  different axis: schema authoring is deliberate and low-volume, so strict feedback there is more useful
  than silent rewriting, while bulk data entry stays lenient. That asymmetry is intentional, not an
  inconsistency — but note it **partially converges with cubic's open P2** on the PR, which argues for
  rejecting `/32` everywhere. Deciding this one way for `default_value` does not settle the value path.
  T010's "a `/32` `default_value` is normalised to bare" case inverts to "raises" as a result.
- **Deleting `test_allow_prefix_cannot_be_updated`** removes a test on paper. It asserted
  `field.json_schema_extra == {"update": NOT_SUPPORTED}` — a restatement of a constant declared in the
  same repo, which `.agents/rules/testing-python.md` § "Don't test the framework" and § "Assert exact
  expectations" both argue against. The behaviour it claimed to cover is genuinely proven by
  `TestAllowPrefixIsImmutable`, including through the real `/api/schema/load` path.

Also worth acting on in PR 1: the `dns_record.py` fixture was written as a raw dict for two recorded
reasons — it drives the same `mode="before"` coercion path a user's YAML payload takes, *and* it was the
only mypy-clean spelling because `dict[str, bool]` was not in the `parameters` union. **The second reason
is obsolete**: `IPHostAttributeParameters` joins that union in PR 1, so the typed form should now
type-check. The first reason remains a genuine trade-off, so converting is a choice rather than a fix.

### The review commit spans two slices

Commit `43b9e45ef` resolves the three PR-1 annotations, but touches **seven** files, only four of which
exist at PR 1:

| File | Change | Slice |
|---|---|---|
| `core/schema/attribute_schema.py` | validator raises instead of stripping | **1** |
| `tests/helpers/schema/dns_record.py` | typed models; `DNS_RECORD_DEFINITION` → `DNS_RECORD_DICT` | **1** |
| `tests/helpers/schema/__init__.py` | rename propagated to exports and `__all__` | **1** |
| `tests/unit/core/schema/test_iphost_attribute_parameters.py` | expectations inverted; tautological test deleted | **1** |
| `tests/component/core/test_attribute_iphost_allow_prefix.py` | rename only | 2 |
| `tests/component/core/schema_manager/test_manager_schema.py` | rename + expectations inverted | 2 |
| `tests/integration/schema_lifecycle/test_attribute_parameters_update.py` | rename only | 2 |

So PR 1 takes the four-file subset, and the remaining three hunks must be folded into PR 2's versions of
those files when that branch is built — they cannot be cherry-picked as-is, because the files do not
exist yet at PR 1.

**One knock-on worth keeping**: the validator rewrite replaced its use of `_bare_host_address` with an
inline `ip_interface` call. That helper is introduced by PR 3's commit, so the rewrite incidentally
**decouples PR 1 from PR 3** — without it, PR 1 would have shipped a helper with zero callers.

**Unverified**: no tests were run against these changes. The inverted expectations are reasoned, and the
riskiest is `test_manager_schema.py` switching to `pytest.raises(PydanticValidationError, match=...)`
without an anchor, since Pydantic prepends its own preamble to the message. The rejection also moved from
`SchemaBranch.validate_default_values()` (an `infrahub.exceptions.ValidationError` naming the kind) to
Pydantic model validation (a `pydantic.ValidationError` naming only the attribute), which changes both the
exception type and the message shape reaching `/api/schema/load`.

### Deferred to PR 2 — scope notes for when that branch is built

| Annotation | Location |
|---|---|
| "leave this an instance method. staticmethods should only be for methods used outside of the class" | `core/attribute.py`, `IPHost._allows_prefix` |
| "this test file is too big. would be good to move the new tests to their own file" | `tests/component/core/schema_manager/test_manager_schema.py` |
| "I believe that this test loads `dns_record_schema` once every time it runs. it would be better if that were class fixture so that it is only loaded once" | `test_attribute_iphost_allow_prefix.py`, `TestValueValidationAndNormalisation` |
| "should also use class-level fixture for loading schema" | `test_attribute_iphost_allow_prefix.py`, `TestStorageAndDerivedProperties` |
| "use `get_attribute(\"v6_target\").value`. apply this throughout the test" | `test_attribute_iphost_allow_prefix.py`, null-path test |
| "what is this testing? should it just validate the expected properties on the `:AttributeValue` vertex at the database level?" | `test_attribute_iphost_allow_prefix.py`, `test_prefix_containment_still_resolves_a_declared_attribute` |
| "use the typed data, so `NodeSchema()` instead of a dict" | `tests/component/graphql/queries/test_hfid.py` |
| "use the literal value, not the returned one" | `tests/component/graphql/queries/test_hfid.py`, `variable_values={"hfid": returned_node["hfid"]}` |

The last one is stronger than it reads: feeding the returned HFID back means the round-trip passes even
if the returned value is wrong. Asserting the literal `["192.0.2.10"]` **and** the masked
`["192.0.2.10/32"]` is the fix, and it overlaps with the lookup normalisation delivered in PR 3 — so
resolve it with PR 3's behaviour in mind rather than in isolation.

The class-level-fixture items are a genuine cost concern, not polish: the feature suite takes ~138s, and
per-test schema loading is the dominant term.

## Commits that dissolve

| Commit | Disposition |
|--------|-------------|
| `8e92cecd5` | `tasks.md` only → dissolves entirely |
| `f6d1c0486` | Spec-document corrections → fold into the feature branch's spec docs |
| `a7e07b682` | `quickstart.md` corrections → fold into the feature branch |
| `8ad7cd3b1` | The implement report → feature branch, with the caveat below |
| every other commit | Its `dev/specs/.../tasks.md` hunk is dropped |

Dropping the `tasks.md` hunks from all 21 commits is what makes this split tractable: that file is
touched by 15 of them and would otherwise be a conflict on every rebase in the stack.

## Mechanics

**Rebase hotspots.** Two files are touched across PR boundaries and will conflict if the stack is
reordered or if PRs are rebased out of sequence:

- `backend/tests/component/core/test_attribute_iphost_allow_prefix.py` — touched by 5 commits spanning
  PRs 2 and 3. The single most conflict-prone file in the split.
- `backend/infrahub/core/schema/attribute_schema.py` — PR 1 (the schema classes) and PR 3
  (`normalize_query_value`). Different regions, so conflicts should be mechanical.
- `backend/infrahub/core/attribute.py` — two commits, both inside PR 2. No cross-PR risk.

Merging strictly 1 → 5 and rebasing each PR onto the feature branch only after its predecessor lands
keeps all of these trivial.

**`tasks.md` policy.** Recommend that **no child PR touches `tasks.md`**. Ticking boxes per PR would put
15 commits' worth of edits back into the hotspot set for no reviewer benefit. Instead, tick every box in
one commit on the feature branch once the stack has merged. The alternative — each PR ticks only its own
boxes — gives a nice per-PR scope signal at the cost of a conflict on every rebase; not worth it.

**Verifying the split is faithful.** After building the stack, `git diff` between the tip of PR 5 and the
current `bare-ip-attribute-infp-551` should be empty except for `tasks.md` checkbox state and this plan
file. That is the check that no hunk was lost in the resequencing — run it before opening any PR.

## The submodule, under a `release-1.11` base

Basing on the release branch changes the SDK side, and this needs a decision before PR 1 can merge.

**What is true today**, verified:

- `origin/release-1.11` and `origin/develop` both pin the **same** SDK commit,
  `681b458cd324c6eec746bb225135cbb7dd99640e`, which is exactly the tip of SDK `infrahub-develop`.
- The SDK branch tip (`89e406a` when first pushed, `525b28f` now) sits on top of that commit: `merge-base(525b28f, 681b458c) = 681b458c`,
  with **0 commits** present in `681b458c` but absent from `525b28f`. So the pointer bump is a **pure
  fast-forward and reverts nothing** — the regression risk that a release-branch reparent would normally
  raise does not exist here.
- **There is no `infrahub-release-1.11` branch in the SDK repo.** The only release-shaped SDK branch is
  `pog-release-13`, which is unrelated.

**The problem**: root `AGENTS.md` § Submodules documents the convention as "the submodule tracks the SDK
branch *named after* the current Infrahub branch", giving `develop → infrahub-develop` and
`stable → stable`. It says nothing about release branches, and no matching SDK branch exists. So the SDK
PR target is genuinely undetermined. Three options:

1. **Target `infrahub-develop`.** Zero setup, and defensible while both Infrahub branches pin the same
   SDK commit. The wrinkle: an Infrahub *release* branch would then depend on a commit whose only home is
   the develop-tracking SDK branch, so a later divergence between the two SDK lines has no defined
   resolution.
2. **Create `infrahub-release-1.11` in the SDK repo** off `681b458c`, target the SDK PR there, and let it
   merge into `infrahub-develop` separately. Follows the spirit of the convention and keeps the release
   line independently pinnable. Costs one new long-lived SDK branch and a mergeback path.
3. **Cherry-pick into both** SDK lines. Most control, most bookkeeping, and two commits to keep in sync.

Recommend **option 2** if `release-1.11` is expected to take further SDK-affecting changes, **option 1**
if this is the only one. This is a team release-process question rather than something to infer from the
repo, so it is listed as an open decision.

Whichever is chosen, `T045`'s pre-merge check must target the same branch — e.g. for option 2,
`cd python_sdk && git merge-base --is-ancestor HEAD origin/infrahub-release-1.11`.

## Sequencing and external dependencies

1. **Decide the SDK branch question above.** PR 1 bumps the pointer, so this blocks PR 1's merge.
2. **Done** — opsmill/infrahub-sdk-python#1220, targeting `infrahub-develop`, currently at `525b28f`.
3. Rebase the current work onto `origin/release-1.11` and re-run `backend.lint` plus
   `backend.validate-generated` per the rebase note above.
4. Create the feature branch and open all five PRs as a stack, so reviewers can see the whole shape.
5. Merge 1 → 5 in order. Before PR 1 merges, complete `T045`: re-pin the pointer to the merged SDK commit
   and confirm it is an ancestor of the chosen SDK branch.
6. Merge the feature branch into `release-1.11`.
7. **Plan the mergeback.** `release-1.11` reaches `develop` through the normal release mergeback, so this
   feature arrives on `develop` that way rather than directly. Worth confirming that path exists and is
   scheduled — note the repo already carries a `release-1.5-to-develop` branch, so there is precedent for
   mergeback branches being explicit work rather than automatic.

**Carry forward to the feature-branch PR description**: the Principle III deviation (Governance requires
it restated in the PR, and the current PR body has the full text), the four narrowing mitigations, and
the known gaps — the `_create`-path validation bypass, the generic/inheritance divergence where a node
re-declaring an inherited `IPHost` attribute silently resets the flag, and the undeclared-attribute
update-path normalisation gap.

## Open decisions

1. **Changelog placement.** C6 puts the Towncrier fragment in PR 5, which is best for review but breaks
   the convention that a fragment travels with its change. Alternative: land the fragment in PR 2 and let
   PR 5 only extend it. Slightly more conflict risk, more conventional.
2. **Whether to split PR 2.** The create/update seam is clean and the uniqueness-bypass fix arguably
   deserves its own review. Takes the stack to 6.
3. **The implement report's commit references.** `opsmill-implement-report.md` §2 cites SHAs from the
   pre-split history that will not exist afterwards. Either drop the SHA column, or add a note that the
   table describes the original linear history. Recommend the note — the provenance is worth keeping.
4. **Squash vs rewrite for C7.** Squashing `08b4e677a` + `221568c60` is faster; rewriting `08b4e677a` to
   use `parse_schema_path` from the start yields a cleaner history but means reconstructing its tests
   against the new implementation.
5. **Whether the two never-run tests should gate the stack at all.** If CI reveals PR 4 needs
   significant work, it can be dropped from the stack and pursued separately rather than holding up the
   feature — nothing in PRs 1–3 depends on it.
6. **Which SDK branch the SDK PR targets**, given no `infrahub-release-1.11` exists. See the submodule
   section above; recommend creating it if `release-1.11` will take further SDK-affecting changes,
   otherwise target `infrahub-develop`. **This blocks PR 1's merge.**
7. **Whether the changelog fragment should say 1.11.** The docs and SDK compatibility matrix already name
   Infrahub 1.11 / SDK 1.23.0 as the version floor. Now that the feature targets the release branch, the
   Towncrier fragment should be checked against whatever release notes `release-1.11` is accumulating, so
   the entry lands in the right release section rather than the next one.
