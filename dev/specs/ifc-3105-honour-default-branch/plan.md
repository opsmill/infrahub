# Implementation Plan: Honour the Configured Repository Default Branch

**Branch**: `pog-honour-default-branch-ifc-3105` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `dev/specs/ifc-3105-honour-default-branch/spec.md`
**Jira**: [IFC-3105](https://opsmill.atlassian.net/browse/IFC-3105) | **Part of (JPD)**: [INFP-670](https://opsmill.atlassian.net/browse/INFP-670)

## Summary

A read-write repository's configured trunk (`CoreRepository.default_branch`) is read from the graph
only when a worker clones the repository for the first time. Every later construction of the per-flow
repository object on that worker omits the trunk and inherits a silent fallback to Infrahub's own
default branch, so artifact generation, transforms, generators, computed attributes and
proposed-change checks intermittently run against the wrong branch or fail with a missing-ref error
naming a branch the operator never configured.

The plan makes the trunk and the staging status required constructor fields of the read-write
object, removes the fallback and the optional field from the shared base, and resolves both values
in one place: the read-write factories read the repository node once, on the Infrahub branch the
operation runs on, through a resolver that lives beside the classes rather than on them. The shared
factory task every downstream flow uses gains that branch as a required parameter, the factories set
it on the instance so the object reports the branch it was resolved against, and the flows, tasks and
message models that used to carry the trunk stop doing so. The base class answers its three former
uses of the trunk through explicit hooks (trunk mapping, Infrahub-side branch, error-message branch),
with identity implementations on the read-only kind so its fetch-failure path keeps producing
classified errors.

On top of that baseline, two visibility improvements land. The connectivity check performed when a
repository is connected now lists the remote's branch heads and `HEAD` symref in the same
`ls-remote` call and rejects a trunk absent from the remote with a message naming the remote's
actual default branch. And a warning naming each remote branch skipped for colliding with Infrahub's
default branch is recorded in a task log linked to the repository: once by the flow that adds the
repository, and thereafter by a synchronisation run that either imported at least one branch or saw a
commit arrive on the skipped branch itself, so a standing collision costs one entry plus one per push
to that branch rather than one per minute.

## Technical Context

**Language/Version**: Python 3.14 backend (project supports `>=3.12,<3.15`). No frontend, SDK or CLI change.
**Primary Dependencies**: Pydantic 2.12 (repository object, message models), GitPython (`git ls-remote --symref`, push refspec), Prefect (flows, run logger, flow-run tags), Infrahub Python SDK (one `get` per construction).
**Storage**: Neo4j, read only. No schema attribute, migration, GraphQL or REST change.
**Testing**: pytest 9.0 across unit (`backend/tests/unit/git/`), component (`backend/tests/component/git/`), functional (`backend/tests/functional/git/`), integration with a Gogs container (`backend/tests/integration/git/`) and integration-docker (`backend/tests/integration_docker/`). See research.md D7 for the per-requirement placement.
**Target Platform**: Linux server, multi-worker deployment where Git storage is per worker.
**Project Type**: Web service (backend-only change in this feature).
**Performance Goals**: One additional GraphQL read per read-write repository construction, amortised by the existing 30 s factory cache; two per repository per minute on the periodic sync. No new Cypher. Connect-time check adds no round trip (same `ls-remote` invocation, wider pattern).
**Constraints**: No new persistent state in the graph; the skipped-branch warning is reported once at connect and thereafter by a synchronisation run that either imported something or saw the skipped branch's remote head move, because a warning on every cycle would add roughly 1,440 linked tasks a day to a repository with a standing collision. The advance check reads the worker's own remote-tracking refs before the fetch, so it is per worker and a single push may be reported once per worker. Trunk edits after connection remain unvalidated. Message models are internal, but the generated `message-bus-events.mdx` must be regenerated. `GitFileGet.branch_name` is a required new field, which assumes API and task workers are upgraded together; no in-flight message compatibility across versions is required. Existing mypy `disable_error_code` entries for `infrahub.git.base` and `infrahub.git.repository` stay as they are; no new suppressions. The code and the docs describing it ship in one PR so a revert is clean.
**Scale/Scope**: **30 production call sites** across `git/`, `artifacts/`, `transformations/`, `generators/`, `computed_attribute/`, `proposed_change/`, `message_bus/operations/git/` and `webhook/`: **16 `get_initialized_repo` callers** and **14 direct factory callers** outside `git/repository.py` (the two inside it are the factory delegating to the classes). Five of the direct callers need their Infrahub branch named explicitly rather than taken from a model field (research.md D4). Plus two new modules inside `git/` holding symbols moved off the classes; two message models; one flow signature; one knowledge page; two user-doc pages; three changelog fragments. Tests carry the larger share: making `default_branch` and `internal_status` required, and
`infrahub_branch_name` a required factory parameter, reaches **64 construction sites across 23 test
files**, many of which pass `client=None` or a stub client that cannot serve the resolver's graph
read. That migration is its own task, decided per file (construct directly with explicit values for
unit tests, or supply a client that answers the resolver).

The criterion for that count, so it can be reproduced and so a different number is recognised as a
different question rather than a contradiction:

```bash
grep -rn "InfrahubRepository(\|InfrahubReadOnlyRepository(\|InfrahubRepository\.init(\|InfrahubRepository\.new(\|InfrahubReadOnlyRepository\.init(\|InfrahubReadOnlyRepository\.new(" backend/tests
```

64 sites in 23 files, of which 61 go through `.init(`/`.new(` (21 files) and 3 are direct
instantiation (2 files). Verified against `develop` at the commit this spec set landed on. Narrower
patterns give smaller answers — `.init(`/`.new(` alone gives 61 in 21 — which is why the expression is
stated rather than the number alone.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | PASS | No schema, migration or generated-schema change. The `default_branch` attribute keeps its shape; its description change already landed separately. The only generated file touched is the message-bus reference doc, regenerated with `invoke docs.generate`. |
| II. Branch-Safe by Default | PASS | The factory reads the repository node on the Infrahub branch the operation runs on, which is what makes a repository in staging (existing only on its branch) resolve correctly (FR-006). The sync child flow keeps its `infrahub_branch` tag. No cross-branch side effects are added. |
| III. Type Safety & Explicit Contracts | PASS | The trunk and the staging status become required pydantic fields; the status is typed with the existing `RepositoryInternalStatus` enum. New internal values are frozen dataclasses (`RepositoryGraphSettings`, `RemoteRefs`, `SyncReport`). Removing the base-class property lets mypy's enabled `attr-defined` check enforce that no base-class code reads a trunk (FR-004). |
| IV. Test Discipline | PASS | Tests per tier are listed in research.md D7, starting with a failing warm-clone reproduction. No mocks: local `file://` remotes, the Gogs container, and the Prefect test harness. The e2e clause ("pytest-playwright tests MUST be included for all user-facing features") does not apply: this is a backend-only change with no frontend work, and every operator-visible effect rides on UI that already exists — the connect form already renders whatever validation error the API returns, and the node Tasks tab already lists node-tagged runs and renders their logs with severity badges. Nothing new is built in the browser, so there is no browser behaviour to pin. The nearest thing to a UI journey, the connect-time rejection, is covered end to end in the integration tier against Gogs, driving the same GraphQL mutation the form calls and asserting the exact operator-facing message; a Playwright test would add only "the form displays the error the API returned", which is generic form behaviour rather than this feature's. **Owner decision, 2026-09-04**: classified as a backend change, so no deviation is claimed and no sign-off is required. If a reviewer reads the clause more strictly, the fallback is a fixture remote without `main` — achievable, since the integration tier already provisions repositories against Gogs and `file://` remotes, but it would need a Git server inside the e2e stack. |
| V. Query Performance & Efficiency | PASS | One SDK read per construction, cached 30 s per repository, kind, branch and commit on the hot paths. No new Cypher; the connectivity check issues the same single `ls-remote` call with a wider ref pattern. |
| VI. Security & Input Boundaries | PASS | Remote URLs and branch names reach `git` as argument-list entries through GitPython, never through a shell. The rejection message names branches taken from the remote listing and the operator's own input, no internals. Message models gain optional/required plain fields validated by pydantic. |
| VII. Simplicity & Maintainability | PASS | One optional field plus a fallback property is replaced by one required field and three abstract hooks that already exist as concrete methods. No new dependency. Two small modules are added (`git/graph_settings.py`, `git/remote_refs.py`), each a frozen dataclass plus one or two stateless functions moved out of a ~1,200-line base class rather than new behaviour; both are required by `.agents/rules/backend-component-design.md`, which keeps database access off models and does not want a class used as a namespace. The `SyncReport` and `RemoteRefs` dataclasses each serve a producer and a consumer that exist in this change. |

### Frontend principles

Not applicable. The node Tasks tab already lists runs tagged with the node and renders run logs with severity badges; no component, hook or generated type changes.

### Shared Components Inventory

Not applicable (no frontend work).

## Project Structure

### Documentation (this feature)

```text
specs/ifc-3105-honour-default-branch/   (symlink: specs -> dev/specs)
├── plan.md                                  # This file
├── research.md                              # Phase 0: verified state and decisions D1-D9
├── data-model.md                            # Phase 1: object fields, hooks, message models
├── quickstart.md                            # Phase 1: manual and CI validation recipe
├── contracts/
│   ├── repository-object.md                 # constructor, factories, three-question hooks, removed carriers
│   ├── connect-time-trunk-validation.md     # message field, ls-remote listing, pure check, exact messages
│   └── sync-task-log.md                     # SyncReport, warning text, the two carriers and the node-link rule
├── checklists/
│   └── requirements.md                      # spec-quality checklist plus the running amendment log
├── critiques/                               # point-in-time critique records, superseded by later
│   ├── critique-20260903-143257.md          #   rounds and by checklists/requirements.md. Historical
│   ├── critique-20260904-094130.md          #   evidence, not current design: statuses and figures
│   └── critique-20260904-104854.md          #   inside them were true only on their own date
├── spec.md                                  # already present
└── tasks.md                                 # Phase 2 output (NOT created by /speckit-plan)
```

Two more files land in this directory during Phase 1 of implementation and are not present yet:
`baseline.md` (T001, the pre-change test baseline) and `call-sites.md` (T002, the migration
worklists).

### Source Code (repository root)

```text
backend/
├── infrahub/
│   ├── git/
│   │   ├── base.py                  # drop default_branch_name / default_branch / internal_status; abstract mapping hooks;
│   │   │                            #   create_locally(checkout_ref: str); _raise_enriched_error passes branch_name through;
│   │   │                            #   check_connectivity removed (moves to remote_refs.py); the static error classifier stays
│   │   ├── graph_settings.py        # NEW. RepositoryGraphSettings + module-level resolve_graph_settings; the single
│   │   │                            #   resolution point, kept off the pydantic model per .agents/rules/backend-component-design.md
│   │   ├── remote_refs.py           # NEW. RemoteRefs + list_remote_refs + ensure_branch_exists; three module-level symbols,
│   │   │                            #   no repository instance state, replaces base.check_connectivity
│   │   ├── repository.py            # InfrahubRepository: required default_branch + internal_status, init/new call
│   │   │                            #   resolve_graph_settings once and set infrahub_branch_name from their parameter,
│   │   │                            #   mapping hook implementations, skipped_branches collection;
│   │   │                            #   validate_remote_branch moves here, returns BranchSkipReason | None (predicate
│   │   │                            #   stays at the decision point, caller never re-tests it);
│   │   │                            #   collect_pending_imports captures the remote heads before fetch() and records
│   │   │                            #   which skipped branches advanced (cold clone records none);
│   │   │                            #   InfrahubReadOnlyRepository: identity hooks; get_initialized_repo(infrahub_branch_name)
│   │   ├── sync.py                  # RepositoryAdder.add without trunk kwargs;
│   │   │                            #   RepositorySyncer.sync -> SyncReport(skipped_branches, imported_branches,
│   │   │                            #   advanced_skipped_branches), report attached to the raise so a partial import
│   │   │                            #   failure still reports
│   │   ├── models.py                # CollectedImports.skipped_branches + advanced_skipped_branches;
│   │   │                            #   remove GitRepositoryAdd.default_branch_name,
│   │   │                            #   GitRepositoryMerge.default_branch
│   │   └── tasks.py                 # add_git_repository: warning per skipped branch (already node-tagged, runs first sync);
│   │                                #   (emitted on the failure path too); GitRepositoryAdd.internal_status stays: it is
│   │                                #   flow control for the staging early return, not a trunk carrier;
│   │                                #   sync child flow: no trunk/status params, construction moves INSIDE the try so a
│   │                                #   failing node read is still node-tagged, warning + node link only when a branch was
│   │                                #   skipped AND something was imported, single add_tags;
│   │                                #   bootstrap/sync helpers stop forwarding node values; every get_initialized_repo
│   │                                #   caller passes infrahub_branch_name; git_branch_create/delete resolve on
│   │                                #   registry.default_branch (the Infrahub branch is gone when delete fans out);
│   │                                #   merge_git_repository: fifth direct init caller, drops model.default_branch and
│   │                                #   passes infrahub_branch_name=model.destination_branch
│   ├── repositories/create_repository.py        # post_create: connectivity message carries default_branch (read-write only);
│   │                                            #   add model without default_branch_name
│   ├── core/merge/repository_merge_dispatcher.py # merge model without default_branch
│   ├── message_bus/
│   │   ├── messages/git_repository_connectivity.py   # default_branch: str | None
│   │   ├── messages/git_file_get.py                  # branch_name: str
│   │   └── operations/git/
│   │       ├── repository.py        # connectivity flow: list refs, optional trunk check; fetch/branch_deleted pass branch
│   │       └── file.py              # pass message.branch_name to the factory
│   ├── api/file.py                  # populate GitFileGet.branch_name
│   ├── artifacts/tasks.py           # pass branch to get_initialized_repo
│   ├── transformations/tasks.py     # pass branch to get_initialized_repo (two flows)
│   ├── generators/tasks.py          # pass branch to get_initialized_repo
│   ├── computed_attribute/tasks.py  # pass branch to get_initialized_repo
│   ├── proposed_change/
│   │   ├── tasks.py                 # pass branch to get_initialized_repo (two sites); _validate_repository_merge_conflicts
│   │   │                            #   uses the factory with the source branch
│   │   └── branch_diff.py           # pass branch to get_initialized_repo
│   └── webhook/models.py            # read-write init through the factory; the Infrahub branch is
│                                    #   context.branch or registry.default_branch, never repo.default_branch (the trunk)
└── tests/
    ├── unit/git/
    │   ├── test_git_repository.py               # construction rejection, read-only fetch classification, mapping hooks,
    │   │                                        #   webhook branch resolution, worktree identifier under a non-main
    │   │                                        #   Infrahub default, validate_remote_branch's skip reasons,
    │   │                                        #   collect_pending_imports records skipped_branches at both call sites,
    │   │                                        #   message models declare no trunk field, _update_operational_status
    │   │                                        #   writes on the branch the factory set
    │   ├── test_graph_settings.py               # NEW. resolve_graph_settings returns node values on the branch it was
    │   │                                        #   given; SDK errors wrapped as RepositoryError with the cause preserved
    │   └── test_remote_refs.py                  # NEW. ref listing (populated / empty / detached HEAD) and the pure
    │                                            #   trunk check; no repository object constructed
    ├── component/git/
    │   ├── test_git_repository.py               # adapt non-main write-back test to construct with the trunk; add the
    │   │                                        #   merge write-back case with model.default_branch gone
    │   ├── test_sync_repository.py              # warning once at connect; idle cycle silent and unlinked; cycle that
    │   │                                        #   imported records it; cycle that saw the skipped branch advance
    │   │                                        #   records it having imported nothing; absent once the collision
    │   │                                        #   lifts; connect-time warning survives a first sync that failed
    │   │                                        #   another branch
    │   └── conftest.py                          # fixtures construct with default_branch / internal_status
    ├── functional/git/test_repository_default_branch.py   # warm-clone reproduction (first task), staging + non-default trunk,
    │                                                      #   proposed-change checks incl. merge-conflict validation on a
    │                                                      #   non-default trunk, node link on the sync child run, node link
    │                                                      #   when the node read fails
    ├── integration/git/test_git_live_remote.py  # connect rejected (master-only remote), retry succeeds, unreachable unchanged
    └── integration_docker/test_artifact_composition.py    # add a warm-clone regeneration step on the production trunk,
                                                           #   asserting the artifact's content matches the trunk's tree (SC-006)

dev/knowledge/backend/
├── git-sync.md                                  # refresh the branch-import section, which names validate_remote_branch
│                                                #   and its bool return and goes stale otherwise (unconditional)
└── git-integration.md                           # repository object lifecycle (FR-011) IF PR #10525 has merged: update its
                                                 #   IFC-2870 volatile section plus the trunk-resolution section, the
                                                 #   construction-paths table, the internal_status and cache-key references
                                                 #   this change falsifies. Otherwise the lifecycle goes to git-sync.md and
                                                 #   #10525 is revised before it merges. Leave its INFP-670 volatile
                                                 #   sections alone
docs/docs/git-integration/
├── connect-repository.mdx                       # connect-time rejection and its message; plus the trunk-edit limitation
│                                                #   the spec and quickstart both cite this page for
└── overview.mdx                                 # where the skipped-branch warning appears
docs/docs/reference/message-bus-events.mdx       # regenerated
changelog/
├── +ifc-3105-warm-clone-default-branch.fixed.md
├── +ifc-3105-connect-time-trunk-validation.added.md
└── +ifc-3105-skipped-branch-task-log.added.md
```

**Structure Decision**: Backend-only change inside the existing `backend/infrahub/git/` package and
its callers. The object contract change lives in `git/base.py` and `git/repository.py`; the flow
and message changes in `git/tasks.py`, `git/sync.py`, `git/models.py` and the two message modules;
every other touched file is a call site adopting the new factory signature. Tests mirror the source
layout at the tier research.md D7 assigns.

Two small modules are added inside the same package, both for the same reason: the symbol has no
repository instance state and the project's component-design rule keeps it off the model.
`git/graph_settings.py` holds the trunk/status resolver and its frozen result;
`git/remote_refs.py` holds the remote listing, its frozen result and the pure trunk check. Each is a
dataclass plus one or two functions, and each is imported by exactly the code that needs it — the
factories and the connectivity flow respectively.

## Complexity Tracking

| Deviation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Three abstract hooks on the base instead of one property (Principle VII) | The read-only kind has no trunk (FR-004), yet `pull`, `reset_to_commit` and `create_locally` on the base need the mapping for the read-write kind. | Keeping a `str \| None` trunk on the base preserves the fallback in spirit and forces a `None` branch in every reader; branching on `isinstance` inside the base violates the dispatch guideline. The hooks already exist as concrete methods; only their declaration moves. **Also rejected: a single injected `BranchNameMapper` collaborator** (a trunk implementation and an identity one) — structurally the cleanest shape, since the three hooks are one concept and the read-only kind implements all three as identity, but it means a new required constructor parameter threaded through the same factories this change is already reshaping, for zero behavioural gain in a bug fix. Handed to `dev/specs/infp-546-git-solid-refactor` alongside the Story 6 update this feature already owns. |
| Two new modules inside `git/` (Principle VII) | `resolve_graph_settings` is database access, which `.agents/rules/backend-component-design.md` keeps off models for new code; `list_remote_refs` and `ensure_branch_exists` have no instance state and are used by a flow that holds no repository object. | Leaving the resolver as a classmethod on the pydantic model adds persistence to a model the rule explicitly excludes, and makes the single resolution point untestable without constructing a repository. Leaving the listing on the base uses the class as a namespace, forces the connectivity flow to name a concrete kind to reach it, and splits a cohesive stateless pair across a class attribute and a module function. Each module is a frozen dataclass plus one or two functions; nothing new is invented, the symbols move out of a ~1,200-line class. |
| A redundant graph read in `bootstrap_local_repository` (Principle V) | The periodic sync already holds the `CoreRepository` node and today forwards its trunk into the factory. FR-003 forbids any flow from supplying the trunk, so the factory re-reads a node the caller has in memory: one extra small `get` per read-write repository per minute. | Letting bootstrap keep forwarding the value is precisely the carrier FR-003 exists to delete, and every such carrier is a place the next caller can forget, which is how this defect arose. The read is amortised nowhere on this path, but the flow already issues several queries per repository. Recorded so the carrier is not reintroduced as an optimisation in review. |
| Two carriers for one warning (Principle VII) | FR-008 needs the skipped-branch condition reported once, not once per minute. A single carrier cannot do both: the add flow runs exactly once per repository but never sees a branch that appears later, and the sync flow sees everything but runs every minute. | Reporting only from the sync flow either floods the task history (rejected on volume) or needs persistent state to de-duplicate, which crosses the GraphQL schema gate this feature avoids. Reporting only from the add flow misses a colliding branch pushed after connection. The two carriers share one warning string and one predicate, so the duplication is a call site, not logic. |
| Two triggers on the sync carrier (Principle VII) | The import-count trigger alone reports at the wrong moments: it fires when an unrelated branch imported, and is silent when the operator pushes to the branch that is not being imported, which is when they are actually waiting for something. FR-008 and SC-004 now require both. | A single trigger cannot cover both moments, and the two are genuinely different events. Rejected alternatives: keep only the import trigger (leaves the feature silent at its most actionable moment, which is the defect this row exists to fix); keep only the advance trigger (a repository whose colliding branch is frozen while other branches are active goes silent after connect, widening the dormancy gap the spec already accepts). The second trigger costs one `{branch: commit}` map captured before the existing `fetch`, no new dependency and no extra network call, and both triggers feed one predicate at one call site. Its per-worker duplication is documented in the spec's Assumptions rather than solved, because solving it needs shared state. |

## Phase 0 / Phase 1 outputs

- [research.md](./research.md): verified code state, the three-question classification, decisions
  D1 to D9 (single resolution point, constructor requiredness, base-class hooks, factory branch
  parameter, connect-time listing, sync task-log report, test placement, documentation, type-checker
  debt).
- [data-model.md](./data-model.md): field-level target state of the repository classes, the new
  frozen dataclasses, message-model and flow-parameter changes.
- [contracts/repository-object.md](./contracts/repository-object.md): constructor and factory
  signatures, hook semantics table, error path, removed carriers and the grep that proves it.
- [contracts/connect-time-trunk-validation.md](./contracts/connect-time-trunk-validation.md):
  message field, `ls-remote` invocation and parsing, verbatim rejection messages, flow mapping.
- [contracts/sync-task-log.md](./contracts/sync-task-log.md): `SyncReport`, verbatim warning text,
  the two carriers (once at connect, then for a cycle that imported something or saw the skipped
  branch advance), the pre-fetch head capture and its cold-clone rule, the node-link rule and the
  observable outcomes.
- [quickstart.md](./quickstart.md): manual scenarios per user story and the local gate to run
  before pushing.

## Risks and follow-ups

- **Widest blast radius is the factory signature.** Every `get_initialized_repo` caller changes; a
  missed caller fails at call time with a clear `TypeError`, not silently. Five callers need a branch
  named explicitly rather than taken from a model field (`GitFileGet`, the branch-deleted refresh,
  both git branch-lifecycle tasks, and `merge_git_repository`); all are addressed in research.md D4.
- **The trap is a call site that has a branch but the wrong one.** A `TypeError` catches an omission;
  nothing catches passing the trunk where an Infrahub branch belongs, or passing the wrong one of two
  branches a model carries. The transform webhook is the first instance and is corrected explicitly;
  `merge_git_repository` is the second, and it is the easiest to miss because it does not go through
  `get_initialized_repo`. The three-question table in `contracts/repository-object.md` is the check to
  apply to every touched call site, exhaustively — the table earns nothing if a site is skipped.
- **`operational_status` moves branch.** The factories now set `infrahub_branch_name`, which
  `_update_operational_status` reads (`git/base.py:247`). Every `get_initialized_repo` caller
  previously left it `None` and wrote the status on the platform default branch; those writes now
  land on the operation's branch. This is the intended shape (one branch, one meaning) and is pinned
  by a unit row in D7, but it is an operator-visible change riding along with a bug fix and belongs in
  the PR description.
- **Warm-clone paths gain a graph read.** Operations that previously succeeded on a warm clone with
  the API degraded now need one GraphQL read at construction. The 30 s factory cache limits this on
  the hot paths but not on the refresh fan-out flows. The read is wrapped as `RepositoryError` so
  existing per-repository isolation keeps working.
- **Behaviour preserved for read-only repositories** relies on identity hooks matching what the
  fallback computed. Unit tests pin both kinds' hook outputs.
- **`ls-remote` pattern change**: switching from `--tags` to `HEAD` plus `refs/heads/*` changes the
  listing size, not the failure modes. Connection and credential failures raise before parsing.
- **Refactor overlap**: `dev/specs/infp-546-git-solid-refactor/` Story 6 planned an optional trunk
  constructor parameter with a global fallback; this feature supersedes it with a required field.
  Updating that spec's Story 6 is a task in this feature, not a note, and expect a rebase on
  whichever of the two lands second. The same task adds the `BranchNameMapper` extraction to that
  spec: the three abstract hooks D3 introduces are one concept, and collapsing them into a single
  injected collaborator is behaviour-preserving structural work, which is that spec's remit rather
  than this one's.
- **PRD and epic amendment is a task, not a note.** The PRD (Confluence Product page 858357761) and
  IFC-3105 are still the source of record and still describe a superseded design. Four corrections,
  all verified against this branch: both open questions are closed (reject at connect; task-log
  warning); P3 is no longer a new repository surface, so the GraphQL "Ask First" gate the PRD
  declares **CROSSED** is not crossed; IFC-2870's "Deterministic reproduction" line names a test
  file, test and `xfail` marker that exist nowhere (research.md, "Tests and fixtures"); and the Out of
  Scope reason for per-commit skipped-branch reporting rests on a premise the code contradicts. Left
  unamended, the next reader of the PRD plans against the design this feature replaced. Not blocking:
  nothing in the code depends on it, and the realistic cost is review friction that T073 already
  covers.
- **FR-011's page depends on a PR outside this feature.** PR #10525
  (`pog-em/git-integration-doc`, draft) adds `dev/knowledge/backend/git-integration.md`, which is the
  page the PRD cites and the natural home for the lifecycle section. It documents the current
  fallback in detail and carries a volatile section naming IFC-2870 and this fix. Whichever of the two
  lands second reconciles: if #10525 is in, T068a edits it; if not, the lifecycle goes to
  `git-sync.md` and #10525 needs revising before it merges, since several of its sections would
  describe deleted code on arrival. The `git-sync.md` branch-import refresh (T068) is unconditional.
- **The PRD's persistent-state requirement is superseded, not outstanding.** PRD FR-008 and SC-004 ask
  for the skipped branch as current repository state, visible for as long as the condition holds. The
  task-log design does not do that for a repository where nothing moves at all once the connect-time
  task ages out. The advance trigger narrows that to a wholly dormant repository; any activity on
  either side of the collision re-reports. **The product owner settled it on 2026-09-04: a dedicated
  status surface for this one condition is overkill.** So the task log is the intended design, the
  residual gap is accepted permanently rather than deferred, and no follow-up is owed. The PRD and the
  epic need amending to match (T071), otherwise the next reader treats it as unfinished work.
- **The advance trigger is per worker and will look like duplication.** One push to the skipped branch
  can produce one task-log entry per worker that later synchronises the repository, because each
  worker compares against its own previous fetch and nothing is shared between them. An operator
  reading the Tasks tab may read this as a bug. It is bounded by the worker count rather than the
  cycle rate, it is recorded in the spec's Assumptions and the contract, and it belongs in the PR
  description alongside the `operational_status` move.
- **Follow-ups to file**: an on-demand configuration-validation action for a connected repository
  (INFP-672); connect-time validation of a read-only repository's `ref`, including tag and commit-SHA
  handling; and the worktree identifier collision when Infrahub's default branch is not `main` and the
  remote has a literal `main`.
