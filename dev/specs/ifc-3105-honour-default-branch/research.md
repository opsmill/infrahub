# Phase 0 Research: Honour the Configured Repository Default Branch

No `NEEDS CLARIFICATION` markers remain. The spec resolved the two product questions (reject at
connect time; report the skipped branch in the task log). This document records what the codebase
investigation found and the technical decisions it drives.

**How to read the code references.** Locations are cited as `module::symbol` where a symbol exists,
and some claims additionally cite a line number. **This is a point-in-time verification record, not a
navigation aid**: it is evidence that a specific fact was checked against `develop` at the commit this
spec set landed on, and the line numbers are part of that evidence. Every one of them was re-verified
at that commit. They will go stale as soon as PR 2 lands, and that is expected rather than a defect
to fix — the symbols stay valid, and the whole point of the decisions below is that most of the cited
code is deleted.

This is the opposite of the standard applied to `dev/knowledge/backend/`. A knowledge page is meant
to stay true, so T068a treats stale line numbers there as something to correct. `tasks.md` follows the
same rule for a different reason, citing sites by symbol only, because a task is read while the code
is moving under it. A Phase 0 record is neither: it is a dated snapshot, and stripping its line
numbers would make its verification unreproducible without making anything more current.

## Verified state of the code

### The fallback and where it bites

- `backend/infrahub/git/base.py::InfrahubRepositoryBase` declares `default_branch_name: str | None`
  and a `default_branch` property returning `self.default_branch_name or registry.default_branch`.
  It is the only fallback of its kind in the module; there are no pydantic validators anywhere under
  `backend/infrahub/git/`.
- `backend/infrahub/git/integrator.py::InfrahubRepositoryIntegrator.init` constructs the object with
  whatever kwargs the caller passed and only consults the graph (via the abstract
  `resolve_checkout_ref`) when the local clone is missing. On a warm clone the graph is never read, so
  a caller that omits the trunk silently gets the platform default. This is the intermittent,
  per-worker defect in the spec.
- `backend/infrahub/git/repository.py::get_initialized_repo` (and its cached inner
  `_get_initialized_repo`, TTL 30 s, keyed on repository id, name, kind and commit) is the factory
  every downstream flow uses: artifact generation, transforms, generators, computed attributes,
  proposed-change checks and user tests, file fetch, the fan-out refresh flows, and the branch-diff
  calculator. It accepts no trunk, no location, no staging status and no Infrahub branch. All of those
  callers therefore run on the fallback whenever the clone is warm.
- Call sites that construct the object directly without a trunk: `git/tasks.py::git_branch_create`,
  `git/tasks.py::git_branch_delete`, `proposed_change/tasks.py::_validate_repository_merge_conflicts`,
  and `webhook/models.py` (both kinds).
- Call sites that pass a trunk today: `git/sync.py::RepositoryAdder.add` (from
  `GitRepositoryAdd.default_branch_name`), `git/tasks.py::sync_git_repo_with_origin_and_tag_on_failure`
  (a required flow parameter), `git/tasks.py::bootstrap_local_repository` (from the node), and
  `git/tasks.py::merge_git_repository` (from `GitRepositoryMerge.default_branch`, optional and left
  `None` by the read-only dispatch). These are the redundant carriers FR-003 removes.

### The three questions one property answers

Every read of `self.default_branch` inside the classes was classified:

| Question | Reads |
|---|---|
| (a) Which remote branch is the trunk | `create_locally` checkout, `get_filtered_remote_branches`, `validate_remote_branch` (collision test and conflict target), `_resolve_worktree_identifier`, `_get_mapped_remote_branch`, `InfrahubRepository.resolve_checkout_ref`, `InfrahubRepository._collect_staging_imports` |
| (b) Which Infrahub branch a commit is recorded against | `create_locally` write-back (`infrahub_branch_name or self.default_branch`), `_get_mapped_target_branch` |
| (c) Which branch name appears in an error or log | `create_locally` error path, `validate_remote_branch` conflict warning, `_raise_enriched_error` (`branch_name or self.default_branch`) |

The read-only trap in the spec is `InfrahubRepositoryBase.fetch`: on failure it calls
`_raise_enriched_error(error=exc)` with no branch name, which evaluates `self.default_branch` on a
read-only object. `fetch` is reached by `init`, by the refresh flow and by `collect_pending_imports`.
The static classifier `_raise_enriched_error_static` already accepts `branch_name=None` (the
connectivity check calls it that way), and only two of its branches use the name: the
`error: pathspec` case (constructs `RepositoryInvalidBranchError`, whose `branch_name` parameter is
typed `str`) and the unmerged-files message.

### Staging status

- `InfrahubRepositoryBase.internal_status: str = "active"` is the object-side staging flag. It is
  supplied only on the four sync-path call sites above and defaulted everywhere else. It is read in
  exactly two places, both on the read-write class: the gate at the top of
  `InfrahubRepository.collect_pending_imports` and the condition in `_collect_staging_imports`.
- The graph attribute `internal_status` on a repository node is branch-scoped: `ACTIVE` on the
  default branch, `STAGING` on the branch the repository was created in
  (`repositories/create_repository.py::RepositoryFinalizer.post_create`). A repository created in a
  branch exists only on that branch until the proposed change merges. Resolving the status from the
  graph therefore requires knowing which Infrahub branch the operation runs on.
- `message_bus/types.py::ProposedChangeRepository.is_staging` is a separate DTO property used once,
  in `proposed_change/tasks.py`, to exclude staging repositories from merge-conflict validation.

### Push refspec (regression coverage, FR-009)

`repository.py::InfrahubRepository.push` already pushes `HEAD:refs/heads/<mapped remote branch>`
from the branch worktree. The trunk worktree lives on disk under the literal identifier `main`
(`_resolve_worktree_identifier`), so a worker that never created a local branch named after the
trunk still has a HEAD to push. Coverage exists in
`backend/tests/component/git/test_git_repository.py::test_merge_writes_back_to_non_main_default_branch`,
which sets `repo.default_branch_name = "develop"` after construction. Under the new contract the
test must construct with the trunk instead; the plan keeps it and adds a mutation check task.

### Connect path

- `graphql/mutations/repository.py::InfrahubRepositoryMutation.mutate_create` creates the node, then
  `RepositoryFinalizer.post_create` sends `GitRepositoryConnectivity(repository_name,
  repository_location)` over the message bus as an RPC, and on `success is False` deletes the node
  and raises `ValidationError(message)`. The API process never runs git; a worker does, in the flow
  `message_bus/operations/git/repository.py::connectivity`.
- `base.py::InfrahubRepositoryBase.check_connectivity` runs `git ls-remote --tags <url>` and discards
  the output. Tags only: the branch heads and the `HEAD` symref are not listed, so the remote's own
  default branch is not obtainable from the current invocation.
- The same RPC backs `graphql/mutations/repository.py::ValidateRepositoryConnectivity` (the
  "Check connectivity" action on an existing repository), which persists `operational_status`.
- The conversion path (`core/convert_object_type/repository_conversion.py`) calls `post_create` with
  `delete_on_connectivity_failure=False` and skips the check entirely.

### Synchronisation task and its log

- The periodic flow `git/tasks.py::sync_remote_repositories` (`git_repositories_sync`, cron every
  minute, concurrency 1) is one flow run for every read-write repository. It carries no
  `infrahub.app/node/<id>` tag, so it never appears in any repository's task history.
- Per repository it calls the child flow
  `git/tasks.py::sync_git_repo_with_origin_and_tag_on_failure` (`sync-git-repo-with-origin`), which
  tags itself with the repository node only when the sync raises and only while the repository is
  `ONLINE`. That child run is the only per-repository carrier on the periodic path, but it runs every
  minute, which is what rules out reporting a standing condition from it unconditionally (D6).
- `git/tasks.py::add_git_repository` (`git-repository-add-read-write`) tags itself with the repository
  node as its first statement, and calls `RepositorySyncer.sync` once after the add completes. It is
  therefore a per-repository carrier that runs exactly once, which is what D6 uses for the
  connect-time report.
- The colliding branch is skipped in `base.py::InfrahubRepositoryBase.validate_remote_branch`, which
  logs "Ignoring import of mismatched default branch" through the module-level structlog logger
  `infrahub.git`. Prefect surfaces only its run logger and the loggers in the worker's task-logger
  set (`infrahub.tasks` plus `workflow.extra_loggers`), so that line never reaches the task log. The
  conflict warning a few lines below already uses `prefect.logging.get_run_logger`.
- The colliding branch survives `get_filtered_remote_branches` (the Infrahub default branch is always
  kept) and is never created locally, so it is classified as a new branch on every cycle and
  `validate_remote_branch` skips it again. A standing collision therefore looks like work on every
  cycle. Two consequences: a per-run warning would recur once a minute, and the early return in
  `collect_pending_imports` for "no new or updated branches" never fires, so the run reaches the
  import loop with `imports` ending up empty. That empty list is the first of the two in-run signals
  D6 uses to tell a cycle worth reporting from one where nothing moved.
- `base.py::InfrahubRepositoryBase.fetch` runs `origin.fetch(prune=True, tags=True, prune_tags=True)`
  with no refspec, so the colliding branch gets a remote-tracking ref like any other, and
  `get_branches_from_remote` already reads that ref's commit into `BranchInRemote.commit` for it. The
  previous head of a branch Infrahub never imports is therefore already on disk in the worker's
  clone, and reading it costs a local ref walk. `compare_local_remote` cannot answer "did it move",
  because it diffs remote heads against *local* branches and the colliding branch has none, which is
  why D6 captures the pre-fetch heads separately. `collect_pending_imports` calls `fetch` at
  `git/repository.py:159`, so the capture point is the statement before it.
- Tags added mid-run with `workflows/utils.py::add_tags` are rebuilt from the tags known at flow
  start, so two in-flow tag updates clobber each other (documented in
  `dev/knowledge/backend/async-tasks.md`). A flow that may link the node for more than one reason
  must issue a single `add_tags` call.
- The frontend Tasks tab on a node (`frontend/app/src/pages/objects/object-details/tasks.tsx`) is
  fed purely by the `related_node__ids` filter, which resolves to the node tag; task logs are read
  from the Prefect log API and rendered with severity badges. No frontend change is needed.

### Tests and fixtures

- No shared fixture creates a remote whose default branch is not `main`; the few tests that need one
  build it inline with `Repo.init(path, initial_branch=...)` (unit, component, functional and
  integration-docker tiers all have an example).
- `backend/tests/functional/git/test_repository_default_branch.py` covers the cold-clone path only
  (the fix shipped for the initial clone). No test exercises a warm clone; the spec's assumption that
  no reproduction exists is confirmed.
- IFC-2870's "Deterministic reproduction" line is the stale triage note the spec refers to. It cites
  `test_initialized_repo_resolves_configured_default_branch` in
  `backend/tests/integration/git/test_multi_env_writeback.py` (PR #9798) as `xfail(strict)`. None of
  it is present: the file does not exist, the test name appears nowhere under `backend/`, and there
  is no `xfail` marker anywhere in `backend/tests/integration/git/` or `backend/tests/functional/git/`.
  Correcting the ticket belongs to the epic-amendment task.
- `backend/tests/unit/git/test_git_repository.py::test_pull_infrahub_default_branch_pulls_repository_default_branch`
  is the only direct coverage of the remote-branch mapping. The collision skip in
  `validate_remote_branch` and the `_get_mapped_target_branch` mapping have no direct tests.
- The Gogs integration fixture (`backend/tests/integration/git/conftest.py`) creates repositories
  whose default branch is `master` and then pushes a `main` branch. A remote with `master` only (no
  `main`) is one API call away, which is exactly the connect-time rejection scenario.
- The Playwright e2e suite exercises repository creation only against the public demo-edge
  repository on GitHub, whose default branch is `main`. This is what the suite has today, not a
  ceiling: the backend integration tier already provisions repositories against a Gogs container and
  local `file://` remotes, so a remote with a non-`main` trunk or none at all is reachable by the same
  means. Bringing it into the e2e stack would mean running a Git server there. Not done, because
  D7 places this feature's coverage in the backend tiers.

### Documentation

- `dev/knowledge/backend/git-integration.md`, cited by the PRD and the epic, is not committed on any
  branch (`git log --all` returns nothing; `origin/develop` has no such file) — **but it exists as
  unpushed work and arrives in PR #10525** (`pog-em/git-integration-doc`, draft, targeting `develop`,
  that one file). Verified against its content: it documents the two `default_branch` namespaces, the
  optional field at `git/base.py:158` and the silent fallback property at `:191-192`, the cold/warm
  path split around `resolve_checkout_ref` being reached only from `git/integrator.py:253`, the
  per-worker storage model, the writeback and divergence gaps, and it carries the volatile section the
  PRD promised, naming IFC-2870 and this fix. It also states `get_initialized_repo` has "roughly
  sixteen call sites", which independently matches the count in D4. So the earlier conclusion here,
  that there was nothing to bring in, was wrong.
- `dev/knowledge/backend/git-sync.md` (2.1 KB, three sections) already documents the branch mapping
  and the collision skip. Its branch-import section becomes wrong under D3 and D6 whatever happens to
  PR #10525, so its refresh is unconditional.
- User docs mentioning the trunk: `docs/docs/git-integration/overview.mdx` and
  `docs/docs/git-integration/connect-repository.mdx`.
- The `default_branch` attribute description change (PR #10449) has already landed on this branch
  (`changelog/+repository-default-branch-description.changed.md`).

### Type checking

mypy disables `arg-type` and `return-value` for `infrahub.git.base`, and `arg-type`, `assignment`
and `call-overload` for `infrahub.git.repository`. `attr-defined` is enabled for both, so once the
`default_branch` property leaves the base class, every remaining base-class read fails type checking.
That is the mechanism behind FR-004's "type checking passing with the trunk absent from the shared
base".

### Overlap with the Git module refactor

`dev/specs/infp-546-git-solid-refactor/` is behaviour-preserving and touches the trunk only in its
Story 6, which proposes keeping `default_branch_name` optional with a global fallback for test
injection. This feature supersedes that item: the trunk becomes a required constructor field, which
gives tests the same injection without a fallback. The two efforts do not otherwise conflict, but
both edit `git/base.py`, `git/repository.py` and `backend/tests/unit/git/`, so whichever lands
second rebases.

**One item is handed to that spec rather than done here.** D3's three abstract hooks are one cohesive
concept — how this repository's remote branch names and Infrahub's map onto each other — and the
read-only kind implements all three as identity, which is a subclass satisfying an interface it has
no concept of. The structurally cleaner shape is a single injected `BranchNameMapper` with a trunk
implementation and an identity implementation, which would also stop `InfrahubRepositoryBase` (~1,200
lines) from growing three more methods. It is deliberately not done here: the hooks already exist as
concrete methods, so declaring them abstract is by far the smaller diff for a bug fix, and injecting
a collaborator would push a new required constructor parameter through the same factories this
feature is already reshaping. The extraction is added to `infp-546`'s scope alongside the Story 6
update this feature already owns.

## Decisions

### D1. The trunk and the staging status are resolved from the graph inside the read-write factory

**Decision**: `InfrahubRepository.init` and `InfrahubRepository.new` (the only two ways a read-write
object is built outside tests) read the repository node once, on the Infrahub branch the operation
runs on, and pass its `default_branch`, `internal_status` and `location` into the constructor. The
read is a single SDK `get` of `CoreRepository` by id on that branch, wrapped in one small resolver in
its own module, `backend/infrahub/git/graph_settings.py`. Nothing else in the system supplies the trunk: `GitRepositoryAdd.default_branch_name`,
`GitRepositoryMerge.default_branch` and the `default_branch_name` and `internal_status` parameters of
the sync child flow are removed, and `bootstrap_local_repository` stops forwarding node values.

**Rationale**: FR-001 and FR-003 require one resolution point and forbid flows and models from
carrying the trunk. Resolving at construction covers the warm-clone path that the cold-clone fix
missed, and every downstream flow inherits the fix through the factory. Reading the node on the
operation's branch is what makes a staging repository (which exists only on its branch) resolvable,
satisfying FR-006.

**Cost**: one extra GraphQL read per read-write construction. `get_initialized_repo` already caches
the object for 30 s per repository, kind and commit, so the hot paths pay once per cache window. The
periodic sync pays two reads per repository per cycle (bootstrap and the child flow) on a flow that
already issues several graph queries per repository. Accepted as the price of a single resolution
point; the alternative of letting the parent sync flow keep forwarding node values is exactly the
carrier FR-003 removes.

**Error contract**: the resolver's SDK call raises the SDK's own exceptions (`NodeNotFoundError`,
`BranchNotFoundError`, `GraphQLError`, `ServerNotReachableError`), none of which derive from
`infrahub.exceptions.RepositoryError`. Every existing caller of the factories isolates failures by
catching `RepositoryError` and `CommitNotFoundError`, so an unwrapped SDK failure would escape
`bootstrap_local_repository` and the sync flows and abort the whole periodic sync instead of skipping
one repository. `resolve_graph_settings` therefore catches the SDK's base `Error` and re-raises
`RepositoryError(identifier=repository_name, message=...) from exc`. A missing node and a missing branch are both
single-repository configuration failures, which is exactly the shape those handlers expect.

**Why the resolver is a module, not a method on the repository class**:
`.agents/rules/backend-component-design.md` puts database access behind a collaborator rather than on
the model — *"For new code, database access and (de)serialization do not belong on the model … prefer
adding a Repository/Query rather than another method on the model."* `InfrahubRepository` is a
pydantic model, so a `resolve_graph_settings` classmethod on it would be new persistence code on a
model. `git/graph_settings.py` holds `RepositoryGraphSettings` and one module-level
`async def resolve_graph_settings(client, repository_id, repository_name, infrahub_branch_name)`;
the factories call it. The `repository_name` parameter is what the wrapped
`RepositoryError(identifier=...)` needs, and a classmethod on the class would not have had it either.
The single resolution point FR-003 asks for is unaffected by where the function lives — and off the
model it is testable with a stub client and no repository object, which is what D7's resolver and
error-contract rows want.

**Alternatives considered**: keep the fallback but always call `resolve_checkout_ref` in `init`
(fixes the warm clone but leaves the optional field and the silent default in place, failing FR-002);
resolve only in `get_initialized_repo`, which leaves the four direct `init` callers on the fallback
(`git/tasks.py::git_branch_create`, `git/tasks.py::git_branch_delete`,
`proposed_change/tasks.py::_validate_repository_merge_conflicts` and `webhook/models.py`); letting the
SDK exceptions propagate unwrapped (turns a one-repository misconfiguration into a failed sync cycle
for every repository).

### D2. Requiredness is enforced by the constructor

**Decision**: `InfrahubRepository` declares `default_branch: str` and
`internal_status: RepositoryInternalStatus` as required pydantic fields with no defaults.
`InfrahubRepositoryBase` loses `default_branch_name`, the `default_branch` property and
`internal_status`. `InfrahubReadOnlyRepository` keeps `ref` and gains nothing.

**Rationale**: FR-002 and FR-005 ask for rejection at construction. A required pydantic field raises
on omission with no code of ours to forget. Typing the status as the existing
`RepositoryInternalStatus` enum follows the guideline that a closed value set is an enum, and
pydantic coerces the string the graph returns. The two comparisons that read the status switch from
`.value` strings to enum members.

**Alternatives considered**: a `model_validator` on the base that rejects a missing trunk only for
the read-write kind (more code, same effect, and keeps the field on the base); keeping the field a
`str` (leaves typos undetectable).

### D3. The base class answers the three questions through explicit hooks, not through the trunk

**Decision**:

- Question (a), the trunk: the three mapping methods `_get_mapped_remote_branch`,
  `_get_mapped_target_branch` and `_resolve_worktree_identifier` become abstract on the base. The
  read-write class implements the existing mapping against `self.default_branch`; the read-only
  class implements identity. `get_filtered_remote_branches` expresses the always-imported set as
  `{registry.default_branch, self._get_mapped_remote_branch(registry.default_branch)}`, which
  evaluates to the current behaviour for both kinds. `validate_remote_branch` and
  `_collect_staging_imports` are read-write concerns and read `self.default_branch` directly.
  `validate_remote_branch` **moves to the read-write class**: it is reached only through
  `collect_pending_imports`, which is defined on `InfrahubRepository`, so no read-only caller exists.
- Question (b), the Infrahub branch a commit is recorded against: `create_locally` takes a required
  `checkout_ref: str` and records the commit against `infrahub_branch_name` when given, otherwise
  against `registry.default_branch`. The platform default is the honest answer to "which Infrahub
  branch" when no branch was named; it is never the trunk.
- Question (c), the branch name in an error: `_raise_enriched_error` passes `branch_name` through
  unchanged, `None` included. The static classifier omits the branch from the two messages that use
  it when none was given. `fetch` keeps passing no branch.

**Rationale**: FR-004 requires the read-only kind to have no trunk and its fetch-failure path to
keep working. Identity implementations are what the read-only kind computes today (its
`default_branch` always equalled the platform default, so every mapping condition was false), so
behaviour is preserved exactly while the type checker enforces the absence of a trunk on the base.

**Alternatives considered**: keep the property on the base returning `str | None` (every reader
grows a `None` branch and the fallback survives in spirit); move all mapping to the read-write class
and special-case the read-only kind in `pull` and `reset_to_commit` with `isinstance` (violates the
dispatch guideline).

### D4. `get_initialized_repo` takes the Infrahub branch

**Decision**: `get_initialized_repo` and `_get_initialized_repo` gain a required
`infrahub_branch_name: str`, forwarded to the factory and added to the cache key. Most callers pass
the branch their model already carries. Five need the branch named explicitly, either because they
carry none or because their model carries two:

| Caller | Branch it resolves on | Why |
|---|---|---|
| `message_bus/operations/git/repository.py::branch_deleted` (refresh flow) | `registry.default_branch` | The branch the message names has just been deleted |
| `message_bus/operations/git/file.py` | `GitFileGet.branch_name`, a new required field populated by the REST file endpoint from its existing branch parameter | The endpoint is already branch-scoped; the message simply did not carry it |
| `git/tasks.py::git_branch_delete` | `registry.default_branch` | The fan-out runs from `delete_git_branch`, which the branch-delete orchestrator triggers **after** the Infrahub branch is removed. Reading the node on that branch would raise `BranchNotFoundError` and fail every `delete_from_git` cleanup |
| `git/tasks.py::git_branch_create` | `registry.default_branch` | The task runs as part of the branch-create fan-out; the repository node is read for its trunk and location, neither of which is branch-specific for this purpose, and the new branch is not guaranteed to be visible to the worker's client when the task executes |
| `git/tasks.py::merge_git_repository` | `model.destination_branch` | A fifth **direct** `InfrahubRepository.init` caller (`git/tasks.py:734`), today passing `default_branch_name=model.default_branch`. Removing that carrier leaves it with two candidate branches. The merge lands on the destination, and the flow already takes its staging decision from `model.internal_status` rather than from the object, so the object's status never needs to read `STAGING`. Reading on `model.source_branch` would resolve a status the flow does not consult and would tie the write-back to a branch that is about to disappear |

**Rationale**: the node must be read on the branch the operation runs on (D1). Making the parameter
required keeps the decision at the call site instead of a hidden default. Adding the branch to the
cache key is necessary because the staging status differs per branch. The two branch-lifecycle tasks
are the exception that proves the rule: naming `registry.default_branch` explicitly at those call
sites records *why* they differ, which a silent default would have hidden.

**The parameter populates the object's `infrahub_branch_name` field.** The base already declares
`infrahub_branch_name: str | None` (`git/base.py:175`), and the factory parameter would otherwise
shadow it: the object would hold one branch in the field and have been resolved against another,
which is question (b) ambiguous again one layer up. So the factories construct with the value they
read the node on, and the field stops being `None` on the `get_initialized_repo` path.

That has one behavioural consequence, and it is intended rather than incidental.
`_update_operational_status` sends `branch_name=self.infrahub_branch_name or registry.default_branch`
(`git/base.py:247`). Today `_get_initialized_repo` omits the field (`git/repository.py:477`, `:480`),
so every downstream flow writes `operational_status` on the platform default branch regardless of
where it runs. After this change those writes land on the branch the operation runs on, which is the
branch whose repository node the operation actually read. The same applies to the read-only
write-back, which passes the field straight to `update_commit_value`
(`git/repository.py:441-442`, `:460`). `operational_status` is branch-scoped, so this is an
operator-visible move on the surface SC-005 relies on and is pinned by a test (D7).

**Alternative considered**: leave the field unset and use the parameter only for the graph read. That
keeps `operational_status` writing on the default branch, but leaves the object carrying two
different answers to "which Infrahub branch am I", which is precisely what D3 exists to remove. If
the status write must stay on the default branch for an unrelated reason, the fix is for
`_update_operational_status` to name `registry.default_branch` outright rather than to inherit
whatever the field happens to hold.

**The webhook is question (b), not (a)**: `webhook/models.py::TransformWebhook.compute_payload`
currently computes `branch = context.branch or repo.default_branch` and uses it as an **Infrahub**
branch for `get_commit_value` and the transform. That works today only because the fallback resolves
to the platform default. Under the new contract `repo.default_branch` is the trunk, so the expression
becomes `context.branch or registry.default_branch`, and that value is passed both to the factory and
to `get_commit_value`. The trunk never appears here.

**Alternatives considered**: defaulting the parameter to `registry.default_branch` (reintroduces a
silent default and breaks staging repositories, which do not exist on the default branch); porting the
webhook expression literally (turns the trunk into an Infrahub branch name that need not exist, which
is the defect class this feature removes).

### D5. Connect-time trunk validation reuses the connectivity RPC

**Decision**: `GitRepositoryConnectivity` gains `default_branch: str | None = None`.
`RepositoryFinalizer.post_create` sets it from the node for the read-write kind only. The worker-side
check lists `HEAD` and `refs/heads/*` with `git ls-remote --symref` in one invocation, parses the
listing into a frozen `RemoteRefs` (the remote's default branch, if any, and the set of branch names),
and, when a trunk was supplied, raises `RepositoryInvalidBranchError` with a message that names the
absent trunk and the remote's default branch (or states that the remote is empty or has no default
branch). The
`connectivity` flow maps that error to `success=False` with `operational_status=ERROR`, and the
existing `post_create` logic deletes the node and raises `ValidationError` with the message.

**Placement**: `RemoteRefs`, `list_remote_refs` and `ensure_branch_exists` live together in a new
`backend/infrahub/git/remote_refs.py` — one frozen dataclass and two module-level functions. None of
the three touches repository instance state: the listing takes a name and a URL, and the check takes
a `RemoteRefs` and two strings. Putting the listing on `InfrahubRepositoryBase` as a classmethod
would have used the class purely as a namespace and forced the `connectivity` flow — which holds no
repository object — to name a concrete kind to reach it, while splitting a cohesive stateless pair
across a class attribute and a module function. `check_connectivity`'s current placement on the base
is the shape being replaced, not one to preserve. The base class keeps growing otherwise, and the
parser's unit rows (D7) test functions rather than reaching through a class.

**Rationale**: FR-007 requires the check to come from the listing the connectivity check already
performs, with no clone, and to leave the connectivity error unchanged when the remote is
unreachable. `ls-remote` with explicit patterns returns the symref for `HEAD` plus every branch head;
a connection or credential failure raises before any parsing and takes the existing classification
path. The read-only kind tracks a ref, not a trunk, so it passes `None`. The "Check connectivity"
mutation on an existing repository also passes `None`, keeping trunk edits after connection out of
scope as the spec requires, and keeping that action what its name says.

**Empty remote, verified**: `git ls-remote --symref <url> HEAD 'refs/heads/*'` against an empty bare
repository returns **no output at all** and exit status 0, under protocol v0 and v2 alike (tested on
Git 2.52). `ls-remote` does not request the `unborn` ls-refs capability that would advertise an
unborn `HEAD`; only `git clone` does. So an empty remote yields `RemoteRefs(default_branch=None,
branches=frozenset())` with no special casing, and the configured trunk is correctly reported absent.
The message says the remote is empty or has no default branch, which covers both shapes without
claiming to distinguish them.

**Alternatives considered**: a separate RPC or flow for the trunk check (a second round trip and a
second failure path for the same remote); validating in the API process (the API has no git and no
credentials); keeping `--tags` and adding a second `ls-remote` call (two remote round trips).

**Consequence**: the node is still created and then deleted on rejection, as it is for a
connectivity failure today. The observable outcome is that no repository exists after a rejected
request, which is what FR-007 asks for.

### D6. The skipped branch is reported once at connect, then by cycles that imported something or saw it advance

**Why a per-run warning does not work.** `compare_local_remote` diffs the remote heads against the
local ones. The colliding branch is never created locally, so it is reported as a *new* branch on
every cycle, `validate_remote_branch` skips it again, and the early return for "no new or updated
branches" never fires. A standing collision therefore looks like work on every cycle, and a warning
plus a node link on every cycle would add roughly 1,440 linked tasks a day to that repository's task
history. That is the same volume the "tag on every cycle" alternative was rejected for, and the
product owner rejected it during critique.

**The discriminators.** That same mechanism gives a stateless signal. On a cycle where only the
colliding branch is "new", the skip means `CollectedImports.imports` comes back **empty**. On a cycle
that has real work, it is non-empty. "Did this run import anything" is therefore answerable inside
the run, with no state carried between runs and no new schema surface.

That signal alone reports at the wrong moments, though. It fires when some unrelated branch imported,
which is when the operator has no particular reason to be looking, and it stays silent when someone
pushes to the colliding branch and nothing happens, which is the one moment they are waiting for an
import that will never arrive. So a second discriminator is used alongside it: **did the skipped
branch's own remote head move during this run's fetch**. This is answerable in the run too, and
without persisting anything, because the unfiltered fetch keeps a remote-tracking ref for the
colliding branch and the listing already reads its commit (see "Tests and fixtures" above). Capturing
the remote heads immediately before `fetch` and comparing after it is a local ref read.

The cost is that the comparison is per worker. Git storage is per worker and the periodic sync has no
worker affinity, so each worker answers "moved since *my* last fetch" independently and one push can
be reported once per worker that later synchronises the repository. Deduplicating that is shared
state, which is the gate this feature avoids. It is bounded by the worker count rather than by the
cycle rate, which is the volume objection the per-cycle design failed. A worker with no prior clone
has no previous head and does not report on this trigger; the connect-time carrier covers the
first announcement unconditionally.

**Decision**:

- `validate_remote_branch` returns *why* it rejected a branch (`BranchSkipReason | None`) instead of
  a bare `bool`, and moves to the read-write class. The collision predicate stays at the decision
  point; the caller must not re-evaluate it. Re-deriving
  `branch_name == registry.default_branch and branch_name != self.default_branch` inside
  `collect_pending_imports` would hold one predicate in two files, and a drift between them would
  drop the branch while reporting nothing — the defect class this feature exists to delete.
- `InfrahubRepository.collect_pending_imports` records each branch whose reason is
  `DEFAULT_BRANCH_COLLISION` in a new `skipped_branches` field on `CollectedImports`. It calls
  `validate_remote_branch` at two sites (`git/repository.py:178` for new branches, `:211` for updated
  ones); both record.
- `collect_pending_imports` also captures the remote heads by calling `get_branches_from_remote`
  immediately **before** `self.fetch()` (`git/repository.py:159`) and records, in a second new
  `CollectedImports` field, every skipped branch whose head is present in that capture and differs
  afterwards. A branch missing from the capture is not recorded: on a cold clone every branch would
  otherwise look new, and the connect-time carrier already reports unconditionally. The capture is a
  local ref read; no additional network call is made.
- `RepositorySyncer.sync` returns a frozen `SyncReport` carrying both the skipped branch names and
  the branches it imported, **and attaches it to the error raised by `raise_if_branches_failed`**.
  Without that, a run whose imports partly failed would return no report and emit no warning; at
  connect that would break FR-008's "MUST be recorded when the repository is connected" for exactly
  the repositories already in trouble. Both carriers log the warnings before re-raising.
- **At connect**, `git/tasks.py::add_git_repository` emits one warning per skipped branch through the
  Prefect run logger, on both the success and the failure path. That flow already tags itself with
  the repository node and already runs the first `RepositorySyncer.sync`, so this is the guaranteed
  single entry, recorded at the moment the operator connects the repository and is looking at it.
- **Thereafter**, `sync_git_repo_with_origin_and_tag_on_failure` emits the warnings and links the run
  to the repository node only when the report lists a skipped branch **and** the run either imported
  at least one branch or saw a skipped branch's head move. A run that did neither records nothing and
  is not linked for this reason.
- The node link stays a single `add_tags` call per run, issued once both conditions (skipped-and-
  imported, or failed while online) are known.

**Resulting volume** for a repository with a standing collision: one entry when it is connected, then
at most one per push that changed an imported branch, at most one per worker per push that changed
the skipped branch, and zero on cycles where nothing moved on the remote.

**Rationale**: FR-008 wants the warning in the task log of a task linked to the repository with no
persistent state, and now also requires that a cycle where nothing moved stays silent. Splitting the
carrier gives both: the add flow is the one place guaranteed to run exactly once per repository, and
the two in-run signals together separate a real change from the permanent re-detection of an
unimportable branch. The import count carries the case where Infrahub did work; the pre-fetch head
comparison carries the case where the operator did work on the branch Infrahub ignores. Neither
covers the other, which is why both are kept. Returning the names from the collection step, rather than logging inside the base
class, keeps the base class free of flow concerns. A single `add_tags` call respects the tag-rebuild
behaviour of mid-run tag updates.

**Consequence accepted**: per-worker duplication on the second trigger, as set out under "The
discriminators". One push to the skipped branch can produce one entry per worker that later
synchronises the repository, and that cannot be deduplicated without shared state.

**Reversed from the first version of this decision**: that version excluded the second trigger, on the
grounds that a commit pushed solely to the colliding branch changed nothing for Infrahub and that
detecting it "would require remembering the last commit seen on a branch Infrahub deliberately does
not import". The first half describes Infrahub's state rather than the operator's expectation, and
the second half is wrong against the code: the unfiltered fetch means git already remembers it.

**Alternatives considered**: warn on every cycle (the rejected 1,440-a-day volume); log through the
run logger inside `validate_remote_branch` and leave tagging as is (the warning lands in a run no
repository page can find); tag the parent `git_repositories_sync` run with every repository (one run
per minute tagged with every repository, and the tag-rebuild behaviour makes per-repository
`add_tags` calls clobber each other); persist the condition on the repository node so it can be
reported once and cleared (the PRD's original preference, and the honest answer for a standing
condition, but it crosses the GraphQL schema "Ask First" gate this feature is scoped to avoid, so it
is left to the sibling visibility effort INFP-670).

### D7. Test placement

**The standard these rows are measured against.** Test the branch an operation actually targeted, not
how it decided. The historical failure is a silent substitution, so the assertions that carry weight
are on observable outcomes — which tree a transform read, which remote ref a push advanced, which
commit was recorded, which branch a status write landed on — and on the impossibility of constructing
the object in the broken state. A test that asserts a property returns a value proves nothing on its
own.

That pulls against the other ask this table serves, a unit suite per module in the design sketch, and
both are legitimate: the unit rows pin a predicate at its single site so two call sites cannot
disagree, but they are not the evidence a requirement is met. The **⭐ Evidence** rows below are the
outcome-level test each headline requirement ultimately rests on; every other row is support.

| Requirement | Tier | Where | Why this tier |
|---|---|---|---|
| ⭐ **Evidence for FR-001.** Warm-clone reproduction (US1 scenario 1), written first and failing before the fix | functional | `backend/tests/functional/git/test_repository_default_branch.py` | Needs the graph node the factory reads and a local remote on disk; the sibling cold-clone test already lives there |
| Staging plus non-default trunk (US1 scenario 3, FR-006) | functional | same file | Needs a repository node on a non-default branch |
| Construction rejection (FR-002, FR-005) | unit | `backend/tests/unit/git/test_git_repository.py` | Pure construction, no git, no graph |
| Read-only fetch failure keeps its classified error (FR-004) | unit | `backend/tests/unit/git/test_git_repository.py` | A local remote that disappears, no graph |
| Mapping hooks for both kinds (D3) | unit | `backend/tests/unit/git/test_git_repository.py` | Pure functions of two strings |
| `resolve_graph_settings` returns the node's `default_branch`, `internal_status` and `location`, read on the branch it was given (D1) | unit | `backend/tests/unit/git/test_graph_settings.py` | The resolver is the single resolution point; a stub client asserts which branch it queried. Off the model it needs no repository object at all. The "repository factory" module suite |
| `validate_remote_branch` returns `DEFAULT_BRANCH_COLLISION` for the collision, `INVALID_BRANCH_NAME` for a name pydantic rejects, and `None` otherwise (D6) | unit | `backend/tests/unit/git/test_git_repository.py` | Pins the predicate at its single site, which is what stops the caller from re-deriving it |
| `collect_pending_imports` populates `skipped_branches` from the collision reason, at both call sites (D6) | unit | `backend/tests/unit/git/test_git_repository.py` | The "collision reporting" module suite the PRD asks for, below the flow tier |
| The two message models no longer declare a trunk field (FR-003) | unit | `backend/tests/unit/git/test_git_repository.py` or the message-model test module | `assert "default_branch_name" not in GitRepositoryAdd.model_fields` and the same for `GitRepositoryMerge.default_branch`. The "message-model cleanup" module suite; the grep in `quickstart.md` Scenario 3 is a manual recipe and cannot enforce this in CI |
| ⭐ **Evidence for FR-009.** Push to a non-default trunk from a worker with no local branch of that name | component | existing `backend/tests/component/git/test_git_repository.py::test_merge_writes_back_to_non_main_default_branch`, adapted | Already exists; construction changes only. The assertion is on the remote ref the push advanced, which is what the pre-fix refspec got wrong |
| ⭐ **Evidence for US1 scenario 5.** The merge write-back still resolves the trunk once `GitRepositoryMerge.default_branch` is gone | component | same file | `merge_git_repository` is the fifth direct factory caller (D4) and the one whose branch choice is not obvious. Asserts the remote trunk ref advanced with the model no longer carrying a trunk, and that the node was read on `model.destination_branch` |
| Remote ref listing and trunk check (FR-007, FR-010) | unit | `backend/tests/unit/git/test_remote_refs.py` | Local `file://` remotes with `initial_branch="stable"`; includes an empty bare remote, which returns no refs at all. Both symbols are module-level, so no repository object is constructed |
| ⭐ **Evidence for FR-007 and SC-003.** Connect request rejected, retry succeeds, unreachable remote unchanged (US3 scenarios 1, 2, 4) | integration | `backend/tests/integration/git/test_git_live_remote.py` | Real remote (Gogs) whose default branch is `master`, through the GraphQL mutation. Asserts the exact operator-facing message and that no repository remains |
| ⭐ **Evidence for FR-008 and SC-004.** Warning recorded once at connect (US4 scenario 1) | component | `backend/tests/component/git/test_sync_repository.py` | Drives the add flow under `prefect_test_fixture`; asserts one warning in its run log |
| A cycle where nothing moved on any branch records no warning and no node link (US4 scenario 3, FR-008) | component | same file | Both discriminators are empty, `SyncReport.imported_branches` and `advanced_skipped_branches`; asserted directly and through the run log |
| A cycle that imported something records the warning (US4 scenario 4) | component | same file | Push to an imported branch between two cycles |
| A cycle that saw the skipped branch advance records the warning, having imported nothing (US4 scenario 5, FR-008) | component | same file | Push to the colliding branch only between two cycles. The pair with the row above is what pins the two triggers as independent, so neither can be dropped without a red test |
| The pre-fetch capture drives the advance detection (D6) | unit | `backend/tests/unit/git/test_git_repository.py` | A `file://` remote and a warm clone: an unchanged skipped branch records nothing, a moved one records it, and a clone with no prior ref for it records nothing. Pins the cold-clone rule, which is otherwise invisible until an operator sees a spurious warning from a fresh worker |
| Warning absent once the collision lifts (US4 scenario 6) | component | same file | Delete the colliding branch, and separately change the trunk |
| A first sync that fails on another branch still records the skipped-branch warning at connect (FR-008) | component | same file | The report must survive `raise_if_branches_failed`; this is the case that would silently lose the connect-time guarantee |
| Node link on the child run only when a branch was skipped and something was imported (FR-008) | functional | `backend/tests/functional/git/` | Needs the Prefect harness client to read the run's tags |
| A failing node read in the sync child flow links the run to the repository node (D1 error contract) | functional | same file | Asserts the construction sits inside the flow's `try`; the failure must be visible in the repository's Tasks tab, which is what SC-005 promises |
| Factory wraps SDK failures as `RepositoryError` (D1 error contract) | unit | `backend/tests/unit/git/test_graph_settings.py` | A client whose `get` raises the SDK's `NodeNotFoundError` and `BranchNotFoundError`; asserts `RepositoryError` with the cause preserved |
| The factory populates `infrahub_branch_name`, and `_update_operational_status` writes on that branch (D4) | unit | `backend/tests/unit/git/test_git_repository.py` | Pins the one behavioural consequence of the field no longer being `None` on the `get_initialized_repo` path: a stub client asserts the branch the status mutation named for an operation running on a non-default branch. Without this the move is invisible until an operator notices the status on the wrong branch |
| Webhook with no context branch resolves the Infrahub default, not the trunk (D4) | unit | `backend/tests/unit/git/` or the webhook test module | Pure branch-resolution assertion on a non-`main`-trunk repository |
| Worktree identifier when the Infrahub default is not `main` and the remote has a literal `main` (D3) | unit | `backend/tests/unit/git/test_git_repository.py` | Documents current behaviour; the collision itself is a filed follow-up, not fixed here |
| ⭐ **Evidence for SC-001, artifact and transform half.** Artifact generation and transform execution on a non-`main` trunk, warm clone, real worker pool | integration-docker | existing `backend/tests/integration_docker/test_artifact_composition.py` (already uses `initial_branch="production"`) plus a warm-clone regeneration step | The only tier with a worker pool and warm clones. Scoped honestly: this file exercises the artifact and transform path, not the whole matrix. Merge write-back, sync, proposed-change checks and the two branch-assertion rows below carry the rest of SC-001 |
| Proposed-change checks, including merge-conflict validation, against a non-default trunk (US1 scenario 2) | functional | `backend/tests/functional/git/test_repository_default_branch.py` | The one matrix flow whose branch choice is genuinely non-obvious: `_validate_repository_merge_conflicts` constructs with the *source* branch, and `run_check_merge_conflicts` / `run_user_check` in `git/tasks.py` take theirs from a check model. A `TypeError` catches an omitted branch; only an outcome assertion catches the wrong one |
| Generator and computed-attribute flows pass the operation's Infrahub branch to the factory (US1 scenario 2) | unit | `backend/tests/unit/git/` or the owning flow's test module | These two sites are mechanical: the flow already holds the branch and forwards it. Asserting the forwarded value is the residual risk; standing up a generator run or a computed-attribute recompute on a non-default trunk would re-test the shared resolution point at a much higher cost |
| ⭐ **Evidence for SC-006.** The regenerated artifact's **content** reflects the trunk's tree | integration-docker | same file, its own assertion | SC-006 is the PRD's end-to-end scenario and its claim is about content, not about regeneration completing. The trunk's tree and the tree of a branch named like Infrahub's default must differ in the transform's input, and the produced artifact must match the former. A test that only asserts the regeneration did not raise would have passed before this feature too |

The Playwright e2e suite is not extended, and no deviation is claimed for that. This is a
backend-only change with no frontend work: the connect form already renders whatever validation error
the API returns, and the node Tasks tab already lists node-tagged runs and renders their logs, so no
new browser behaviour exists to pin. The integration tier carries the connect journey against Gogs
through the same GraphQL mutation the form calls. See the plan's Constitution Check row for
Principle IV, including the fallback if a reviewer reads the e2e clause more strictly.

### D8. Documentation

- FR-011's lifecycle content is the same either way: the trunk is resolved once at construction from
  the graph by `git/graph_settings.py::resolve_graph_settings`, the factories set
  `infrahub_branch_name` from the branch they read it on, the read-only kind has no trunk, and the
  base class answers the three questions through hooks. **Which page receives it depends on merge
  order against PR #10525**, which brings `git-integration.md` (see "Documentation" under verified
  state).
  - **PR #10525 first**: the content updates `git-integration.md`. That is more than clearing its
    volatile marker. This feature falsifies its "Resolving the trunk on the repository object"
    section outright (D2 deletes both the optional field and the fallback property it quotes at
    `git/base.py:191-192`), all three rows of its "Which construction paths resolve it today" table
    (D1, D4), its `internal_status` default reference under "Staging repositories" (D2), and its
    description of the factory cache key (D4 adds `infrahub_branch_name` to it). Its line-number
    citations into `git/base.py` and `git/repository.py` go stale in bulk.
  - **This feature first**: the content goes to `git-sync.md`, and PR #10525 must be revised before
    it merges, or it lands describing deleted code.
  - Either way, leave its three other volatile sections alone. Post-merge ordering, the push
    writeback and divergence detection are INFP-670 scope, not this feature's.
  - Its "A skipped branch is re-reported every cycle" known limitation is **reframed, not deleted**.
    D6 keeps the structlog line, so the process log still repeats once a minute; what changes is that
    an operator-facing record now exists, at connect and on the two triggers. Deleting the bullet
    would overstate what this feature fixed.
  - No PRD or epic correction is needed for the `git-integration.md` pointer. The PRD was right.
- The same edit must also refresh `git-sync.md`'s **existing** branch-import section, which is not
  merely incomplete but becomes wrong: it names `validate_remote_branch` as the place the skip
  happens and states that it "logs ... and returns `False`". D3 moves that method to the read-write
  class, D6 changes its return type to `BranchSkipReason | None`, and the operator-facing record
  moves from the structlog line to the task log. Scoping the FR-011 edit to "the new lifecycle
  section" would leave the page stale on exactly the facts it exists to record.
- `docs/docs/git-integration/connect-repository.mdx` documents the connect-time rejection and the
  message the operator sees, **and** carries the trunk-edit limitation (a trunk edited after
  connection is not validated, nothing re-clones or reconciles, and the value is cached briefly).
  The spec's edge-case list and `quickstart.md`'s SC-005 table both point at this page for that
  limitation, so it needs a task behind it. `docs/docs/git-integration/overview.mdx` documents where
  the skipped-branch warning appears.
- `docs/docs/reference/message-bus-events.mdx` is regenerated because two message models change
  (`GitRepositoryConnectivity` gains `default_branch`; `GitFileGet` gains `branch_name`).
- Changelog: one `fixed` fragment for the warm-clone defect, one `added` fragment for the
  connect-time validation, one `added` fragment for the task-log warning.

### D9. Type-checker debt

The change removes reads that `arg-type` suppressions may have hidden. Implementation keeps the
existing per-module `disable_error_code` entries unchanged and does not add new ones; if a suppressed
error surfaces in touched code it is fixed rather than re-suppressed. The `ty` file-scoped ignores for
`backend/infrahub/git/**` stay as they are.
