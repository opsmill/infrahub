# Implementation Plan: Git remote writeback failure handling

**Branch**: `gma-20261002-ifc3220` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

**Branches from**: `develop` at `04edcdd3f` | **Prerequisite**: PR #10465, on `develop` as `7d1bab3d1`

**Input**: Jira epic IFC-3220. PRD: Notion `a81228b830258373bc5b81dbb878345c`, Confluence 861896706.

**Revised** after [critiques/critique-20261002-1500.md](critiques/critique-20261002-1500.md).

## Summary

When the remote rejects the push of a merge, Infrahub records nothing on the repository, offers no
retry, does not track the merges that accumulate, and regenerates without waiting for the push.

This plan adds a persisted delivery queue on the repository, as branch-local read-only attributes
written on Infrahub's default branch through one store. Every git-synced merge that carries
repository content appends its inputs to the queue before anything is submitted. One service
delivers the queue: it fetches, checks that nothing it would push was discarded by a rewrite,
replays the pending merges on the fresh remote head, pushes once, records the commit with a durable
import obligation, imports when the remote had moved, broadcasts, and then, outside the repository
lock, releases the held regeneration. `merge_git_repository`, a new retry flow and a recovery check
in the periodic synchronisation call the same service. A Prefect task retries transient failures three
times, and every Git command of the adapter gets a time limit, which does not yet stop a hung fetch
or push (`research.md` R6, open point). While a delivery is pending, no
other path imports the default branch. A regeneration barrier, consulted at every dispatch point of
the merge follow-up, holds the definitions of a repository with a pending delivery as identifiers
with hold sequences, keeps their narrowed selection in the cache for the length of the automatic
retry chain, about 45 minutes, and releases them once, under a lease, when the queue clears. A user with write access can retry, or abandon the queue with a durable record.
The repository page shows the state, read from the default branch, and the two actions.

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.9 with React 19.2 (frontend)

**Primary Dependencies**: FastAPI, Pydantic 2.12, GitPython, Prefect 3.8, `infrahub_sdk`, gql.tada,
urql, React Query

**Storage**: Neo4j through the Infrahub schema layer. Git worktrees on each worker's own disk. The
distributed lock registry for the two locks. The cache for the narrowed selections.

**Testing**: pytest 9.0 unit tests with no database. Component and integration tests through
testcontainers. The Gogs live-remote harness of `backend/tests/integration/git/`, including the
`pre-receive` hook helpers from #10465. Vitest for frontend logic. pytest-playwright for e2e.

**Target Platform**: Linux server, multi-worker

**Project Type**: web service, backend and frontend

**Performance Goals**: on a merge with no pending delivery, the barrier adds one indexed read per
consultation, and the merge dispatcher adds two reads and one write per git-synced repository that
carries content. The synchronisation adds one read per repository per cycle. A delivery adds one
fetch and one ancestry test per queued entry to today's merge and push. SC-008: a merge whose
delivery succeeds within its automatic retry chain regenerates as precisely as today.

**Constraints**: the repository lock is the most contended lock of the Git subsystem. The new
delivery-state lock is held for one read-modify-write, has a 30-second time to live, and is never
held across Git work, so a branch merge never waits for a push. A delivery attempt holds no lock
across a retry delay or a release. Every Git command that the delivery adapter runs gets a time
limit, the local ones included. The limit does not stop a hung fetch or push, and in the runtime
image it stops no direct Git call (`research.md` R6, open point). The import has no bound, and the
Git commands inside it have none either. While the import holds the repository lock, the recovery check starts no second attempt
(`research.md` R6, R20).

**Scale/Scope**: one new package of twelve files (`backend/infrahub/git/writeback/`), two new
modules in `core/merge/`, about twenty-five existing backend modules touched, and one frontend
entity folder, `frontend/app/src/entities/repository/`. The stored history of the queue grows with
the square of the merges in one outage: about 1.2 MB for 100 merges (`research.md` R23). The task
count is in the table at the end of [tasks.md](tasks.md).

## Constitution Check

*GATE: passed before Phase 0 research, re-checked after Phase 1 design and after the critique.*

| Principle | Assessment |
|---|---|
| **I. Schema-Driven Integrity** | Pass. Nine attributes declared in the schema layer. Protocols, the GraphQL schema and the frontend types are regenerated, never hand-edited. |
| **II. Branch-Safe by Default** | Pass, and it is a central decision. `LOCAL` makes the state diff-invisible and never merged. The read inheritance of `LOCAL` is specified (FR-025) and handled: the store reads the default branch only, and no generic UI surface shows the inherited copy. A branch-safety test asserts both. |
| **III. Type Safety & Explicit Contracts** | Pass. The queue, the held set and the records are versioned Pydantic models, not dictionaries. The causes are a closed enum. Per-ref rejections get a typed exception whose reason comes from GitPython's flags. Both contracts are written before implementation. |
| **IV. Test Discipline** | Pass. The classifier, the queue model, the service, the abandoner, the recovery check and the barrier are unit-testable without a database, through four ports. Integration tests run against a live Gogs remote. Two e2e tests cover the user-facing actions. |
| **V. Query Performance** | Pass. The barrier's fast path is one query for every pending repository, not one per definition. The release resolves held identifiers with the selectors' existing queries. No N+1. |
| **VI. Security & Input Boundaries** | Pass with a sign-off. Both mutations refuse off the default branch and check object update, `manage_repositories` and `edit_default_branch` explicitly. The stored message is the remote's own lines and the typed message, never raw stderr, and every URL is scrubbed of credentials. The abandonment record names the account in its value and in the edge metadata. The credential-versus-actor point is a governance item, below. |
| **VII. Simplicity & Maintainability** | Pass with three notes, all in Complexity Tracking. No new node kind, no new event type, no new setting. Rejected on this principle: a Git bundle, a related node, a new trigger, gating inside the transform executor, a separate release workflow, a re-import inside the abandonment, prefix delivery, a liveness heartbeat, and a fallback setting for rollback. |

### Governance gates crossed

| Gate | Status |
|---|---|
| Database schema or migration change | **Yes.** Nine branch-local attributes on `CoreRepository`. Optional with no default, so no data migration and no `GRAPH_VERSION` bump. **Needs sign-off.** |
| GraphQL schema modification | **Yes.** The nine fields and two mutations. **Needs sign-off.** |
| Authentication or authorization change | **Yes.** Two new permission-gated mutations. The delivery uses the repository's stored credential, so a permitted user can cause a push the user could not personally make. A proposed-change merge already does. **Needs sign-off.** |
| New dependency | No |
| CI/CD workflow change | No |
| Submodule change | **Yes, generated.** `python_sdk/infrahub_sdk/protocols.py` is regenerated. It needs its own SDK PR first, shared with IFC-3210, which regenerates the same file. |

### Open governance question

Retry and abandon both need object update, `manage_repositories` and `edit_default_branch`. A user
who merges through a proposed change can lack all three, so the persona of both actions is the
operator who manages repositories. **To confirm**: is that the intended persona, and should a retry,
which only repeats what the merge already asked for, need less than an abandonment?

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3220-writeback-failure-handling/
├── spec.md
├── plan.md                         # this file
├── research.md
├── data-model.md
├── quickstart.md
├── alignment-check.md              # written by the prep alignment phase
├── contracts/
│   ├── repository_delivery.graphql
│   └── internal-interfaces.md
├── checklists/
│   └── requirements.md
├── critiques/
│   └── critique-20261002-1500.md
└── tasks.md                        # written by the tasks phase
```

### Source code

```text
backend/infrahub/
├── git/
│   ├── writeback/                         # NEW
│   │   ├── __init__.py
│   │   ├── constants.py                   # retry bounds, barrier read retries, Git timeouts,
│   │   │                                  # stale bound, cache bounds
│   │   ├── models.py                      # queue, held set, records, intent, outcomes, actor
│   │   ├── classifier.py                  # classify_delivery_failure, scrub_credentials
│   │   ├── ports.py                       # DeliveryStatePort, DeliveryGitPort, RegenerationReleasePort,
│   │   │                                  # DeliveryRunQuery
│   │   ├── store.py                       # WritebackIntentStore, the only read/write path
│   │   ├── git_adapter.py                 # the only Git code of the package
│   │   ├── runs.py                        # delivery run tags, the only orchestrator query
│   │   ├── service.py                     # RepositoryWritebackService.deliver
│   │   ├── abandoner.py                   # WritebackAbandoner.abandon
│   │   ├── recovery.py                    # DeliveryRecoveryCheck.run
│   │   └── factory.py                     # wiring for the flows
│   ├── base.py                            # subtypes, isinstance status map, fetch, worktree and
│   │                                      # branch-deletion timeouts
│   ├── repository.py                      # push: typed rejection, flags, remote lines, timeout;
│   │                                      # reset timeout; sync skip
│   ├── models.py                          # payload fields, PushRejectionReason, new models
│   └── tasks.py                           # merge, retry and abandon flows; bootstrap skip; delete guard;
│                                          # recovery check; repository filters on the blanket flow
├── core/
│   ├── constants/__init__.py              # RepositoryDeliveryStatus, RepositoryDeliveryFailureCause,
│   │                                      # FullRegenerationReason, moved here, with new members
│   ├── schema/definitions/core/repository.py   # the nine attributes
│   ├── merge/
│   │   ├── regeneration_barrier.py        # NEW
│   │   ├── regeneration_release.py        # NEW
│   │   ├── regeneration_dispatcher.py     # barrier at four sites, reasons on the widen markers
│   │   ├── repository_merge_dispatcher.py # enqueue before submit, bounded retry,
│   │   │                                  # per-repository guard, context, state port
│   │   ├── recompute_coalescing.py        # barrier on the Python family
│   │   ├── python_target_sources.py       # owner_of
│   │   ├── builder.py                     # wiring
│   │   └── selective_regen/definition_selector/artifact_selector.py   # repository_id
│   ├── branch/tasks.py                    # wiring of post_process_branch_merge
│   └── recompute/dispatch.py              # wiring of the chain
├── computed_attribute/tasks.py            # barrier in computed_attribute_setup_python
├── generators/tasks.py                    # repository filters
├── message_bus/operations/git/repository.py   # isinstance status map in connectivity
├── exceptions.py                          # four new exceptions
├── graphql/
│   ├── mutations/repository.py            # two mutations, ProcessRepository refusal
│   └── schema.py                          # registration
├── workflows/catalogue.py                 # two workflows
├── workflows/constants.py                 # the delivery marker tag
└── core/schema/generated/, core/protocols.py   # regenerated

frontend/app/src/entities/
├── repository/
│   ├── api/                               # retry-, abandon-, get-delivery-state-from-api.ts
│   ├── domain/                            # use cases, delivery-state model, actions-by-status rule
│   └── ui/                                # delivery section, menu items, abandon modal, queries
└── nodes/object/ and nodes/.../columns/   # keep the nine attributes out of the generic surfaces

backend/tests/
├── unit/git/writeback/                    # classifier, scrubber, models, service, abandoner, recovery
├── unit/core/merge/                       # barrier, release plan building
├── component/git/writeback/               # store, branch safety, no events, data-only skip, long queue
├── component/graphql/                     # mutations: branch and permissions
├── component/core/merge/                  # held regeneration end to end
└── integration/git/test_git_live_remote.py   # the Gogs scenarios

tests/e2e/repository/test_repository_delivery.py   # NEW, retry and abandonment
```

**Structure Decision**: the delivery logic lives in one package, `backend/infrahub/git/writeback/`,
with every Git call behind `git_adapter.py` and every write behind `store.py`. The barrier and the
release live in `core/merge/`, beside the dispatcher they wrap, because they deal in regeneration
requests, not in Git. The service reaches the release only through a port it declares, so
`git/writeback/` never imports the merge layer. This mirrors the shape the sibling epic chose for
`git/divergence/`.

## Delivery order

Each part is testable on its own.

| Part | User story | Depends on | Gate |
|---|---|---|---|
| **A. Typed failures and time limits on Git commands** | Foundation | nothing | none |
| **B. State, schema and store** | Foundation for US1 | A | schema sign-off, SDK PR |
| **C. Queue and first attempt** | US1, some scenarios of US2, US7 #1 and #2 | B | none |
| **D. No other import of a pending destination** | US2 #3 | C | none |
| **E. Automatic retry and recovery check** | US4 | C | none |
| **F. Retry mutation and flow** | US2 | C | GraphQL and authorization sign-off |
| **G. Barrier and release, generators and artifacts** | US3 | C | none |
| **H. Barrier, Python family** | US3 #6 | G | coordinate with IFC-3002 |
| **I1. Abandonment: clear and record** | US5 | C | GraphQL and authorization sign-off |
| **I2. Abandonment: release** | US3 #7 | G, I1 | none |
| **J. Branch-deletion guard and deletion at delivery** | US6 | C | none |
| **K. Frontend** | US1, US2, US5 | F, I1 | none |
| **L. Reverted delivery** | US7 #3 | B, IFC-3210 rewrite classification | IFC-3210 |
| **M. Documentation and e2e** | all | K | none |

**First deployable set**: A, B, C, D, F, G, I1, I2, J and K, plus the recovery path of E: the task
retries (T077), which also retry a failed release, and the recovery check (T079, with its tests in
T080). That gives a visible failure, a working retry, an exit for a stuck queue, no import that
deletes undelivered objects, and no source branch lost. The regeneration of the generators and
artifacts of a pending repository waits for the delivery, and an abandonment releases it. Held work
reaches a release also after a failed release or a crash.

**No deployment ships C without D, G, I1, I2, J, the abandonment UI of K, and the recovery path
of E.** C alone is worse than today:

- Without I1, it queues merges that nothing can clear.
- Without D, it lets the synchronisation delete their objects.
- Without J, it lets the branch deletion remove the commit they need.
- Without G, a merge follow-up regenerates the generators and artifacts of a pending repository
  against the commit recorded before the merge. A later delivery puts the new content on the
  remote, and nothing regenerates them again. Today, Infrahub never delivers a failed push, so the
  remote and the regenerated artifacts both reflect the commit recorded before the merge.
- Without I2, an abandonment never releases the regeneration that G holds.
- Without the recovery path of E, held work can wait until the next delivery of its repository,
  which breaks FR-016. A release that fails needs the task retry of stage `release` (T077). A crash
  between the settle and the clear needs the recovery check (T079 and its tests, T080).

**Next**: the rest of E (T078 and T081 to T084), then H. H needs coordination with IFC-3002. Until
H ships, Python-transform computed attributes are not held, as today. After a delayed delivery, such
an attribute can reflect the commit recorded before the merge until its next recompute. For these
attributes, SC-004 and US3 #6 hold only once H ships.

**What part C changes for everyone.** From part C on, `merge_git_repository` no longer calls
`InfrahubRepository.merge`. It delivers the queue. A merge with no failure behaves as today, plus
one fetch and the ancestry checks. A clone with no `origin` no longer merges and records locally:
the attempt fails and keeps the queue (`research.md` R3). `InfrahubRepository.merge` stays only for
`InfrahubRepository.rebase`, which has no caller, and for the live-remote tests of #10465.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **The hold is the normal path for a git-synced merge that carries content.** | Without the narrowed cache, such a merge would recompute whole kinds. | The narrowed cache of `research.md` R9 keeps SC-008 true for the whole automatic retry chain, and a repeated hold writes a union. The data-only skip of R3 removes every merge that carries no content. A release after the window widens, which is FR-014's intent. |
| **A merge lands during the import of a delivered commit.** | Its repository objects can be deleted, then recreated with new ids at the next attempt. | The obligation stays, so the next attempt imports them. The same exposure exists today between a synchronisation import and a merge. Documented. |
| **The abandonment leaves repository objects that the recorded commit lacks.** | The release can fail for those definitions until a user reimports. | The repository section says so and offers the reimport. An abandonment that removed them would itself fail on the delete validator (`research.md` R8). |
| **Whole-queue abandonment drops good entries.** | Re-delivery needs a manual merge on the remote per dropped entry, since a merged Infrahub branch cannot merge again. | A conflict can also be resolved on the remote, and a retry then clears it. The cost is stated in spec decision 1, for Patrick to confirm. |
| **IFC-3210 changes the same code.** | Conflicts in `collect_pending_imports`, the merge path, the ancestry primitive and the SDK protocols file. | `research.md` R19 says who owns what. Agree the merge order with Patrick. IFC-3210 is recommended first. |
| **The SDK protocols change.** | A pointer to an unpushed SDK commit breaks every checkout. | One SDK PR for both epics, or an agreed order, merged before the pointer moves. Tell IFC-3210 that its data model's "no submodule change" is wrong. |
| **A failure between a release dispatch and the clear.** | The held work regenerates twice. | Accepted. Over-execution is the established direction (ADR 0012). FR-015 and SC-004 state it. |
| **The synchronisation skips the default branch while a delivery is pending.** | A commit pushed directly to the remote default branch is not imported until the queue clears. | The section says so. The delivery imports it. Documented in the user docs. |
| **A branch forked during an outage.** | A later synchronisation import of that branch deletes the pending merges' objects there. | The reimport refuses on every branch. The synchronisation case is a known limitation, documented. |
| **A push failure classification changes on a Git or server upgrade.** | A rejection moves to `unclassified`, which is never retried. | The safe direction. The reason comes from GitPython's flags, and the classifier's table test lists the known cases. |
| **The automatic retry can hold a worker slot for up to about 45 minutes.** | Less worker capacity during a remote outage. | One chain per repository, three retries (four attempts), time limits on Git commands. A persistent outage ends in `action-required` and frees the slot. A hung fetch or push is not stopped by its limit and keeps the slot until the connection ends (`research.md` R6, open point). |
| **Existing tests assert the push rejection message.** | Part A could break them. | The typed error keeps the message byte for byte. |
| **The e2e stack has no Git server.** | The UI journeys cannot use Gogs. | The SDK `GitRepo` helper serves a bare repository, and a `pre-receive` hook in it rejects the push. `research.md` R15. |

## Rollback

A code revert is safe for the data: the attributes are additive, and the old code ignores them.
After a revert, queued entries are never delivered and held regeneration is never released. The
release note tells an operator to deliver or merge again by hand, and to run a full regeneration of
the default branch. No setting falls back to the old merge path (`research.md` R22).

## Settled without asking

| # | Decision | Basis |
|---|---|---|
| 1 | Inside Infrahub, abandonment is the only exit from an unreplayable queue. A manual merge on the remote is the other. | `spec.md` decision 1. To confirm with Patrick. |
| 2 | Provisional label "Push to remote". Names never carry the label. | `spec.md` decision 2. To settle with INFP-671. |
| 3 | The state lives on `CoreRepository`, read and written on the default branch only. | `research.md` R1. |
| 4 | Writes go through the core node API, not the SDK, so they emit no node event. | `research.md` R2. |
| 5 | A second, short lock with a time to live guards the state. | `research.md` R2. |
| 6 | The queue entry carries the source commit from the graph. A merge that carries no content is not queued. | `research.md` R3. |
| 7 | The delivery records, with a prior import obligation, then imports, then releases outside the lock. | `research.md` R4. |
| 8 | Both mutations refuse off the default branch and require what an update of the repository on the default branch requires. | `research.md` R7. |
| 9 | The retry and the abandonment are workflows. The abandonment never imports. | `research.md` R7, R8. |
| 10 | The release runs inline, dispatches first and clears by hold sequence. | `research.md` R10. |
| 11 | A refused remote branch deletion is carried on the entry and done at delivery. | `research.md` R12. |
| 12 | `RequestArtifactDefinitionGenerate` gains `repository_id`, which corrects a PRD claim. | `research.md` R0, R9. |
| 13 | The narrowed selection lives in the cache for the length of the retry chain, as a union over repeated holds. | `research.md` R9. |
| 14 | The periodic synchronisation restarts a lost attempt and an owed release. | `research.md` R20. |
| 15 | Recomputes from live events of other writers, and transform webhooks, are not held. | `spec.md` decision 14. |
| 16 | The end of an attempt has the shape of the abandonment: entries settle under the repository lock, then a leased release runs. | `research.md` R4, R10. |
| 17 | The barrier also holds runs that no merge started, on the default branch, while a delivery is pending. | `research.md` R9. |
| 18 | After an abandonment, a kept source branch comes back as a new Infrahub branch on every worker. | `research.md` R12. To confirm with the product owner. |

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| A second lock, `repository-delivery`, which is new coordination state (Principle VII). | The barrier's check-and-hold and the delivery's take-and-clear must not interleave, or held work is dropped (`research.md` R2). The branch merge flow must not wait for Git. | The repository lock makes a branch merge wait behind a sync or a push. A compare-and-set query is more code and has no precedent for node attributes here. |
| Four JSON attributes, which are structured values (Principle VII, and the sibling's rejection of a structured record). | The queue and the held set are lists by nature, and an abandonment record carries a list of entries. | One attribute per entry field cannot hold a list. A related node per entry is diff-visible and needs its own permission model, which the PRD rejects. The status, the cause, the message and the last commit, which a server-side query or a display needs, stay scalar. |
| A cache of narrowed selections, which is a second store for held work (Principle VII). | Without it, nearly every git-synced merge that carries content would recompute whole kinds (SC-008). | Persisting the narrowing in the graph breaks FR-014. Waiting for the first attempt delays every git-synced merge, by minutes when the remote is down. A miss only over-executes. |
