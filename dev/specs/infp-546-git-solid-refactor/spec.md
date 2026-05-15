# Feature Specification: SOLID Restructuring of the `infrahub.git` Module

**Feature Branch**: `git-solid-refactor-infp-546`
**Jira**: INFP-546 — *Refactor git modules within Infrahub to be more Solid* (Epic: IFC-2533)
**Created**: 2026-05-11
**Status**: Draft
**Input**: User description: "Restructure the `infrahub.git` module to follow SOLID principles. Iterative, behavior-preserving work — no logic changes at this stage. Each step must leave the codebase in a working, deployable state with the public API intact."

## Context & Motivation

The `infrahub.git` module is the integration surface between Infrahub and Git repositories. It is responsible for cloning, fetching, branching, merging, importing repository-defined objects (schemas, GraphQL queries, transforms, checks, artifact definitions, generators), rendering artifacts, and executing repository-defined Python code. It is one of the most heavily-imported modules in the backend.

Today, that responsibility is concentrated in two very large classes joined by an inheritance chain. Maintainability has degraded to the point where:

- A single class owns approximately 1,500 lines and combines five distinct responsibilities (config parsing, file discovery, object lifecycle, artifact rendering, dynamic Python loading).
- Adding a new importable object type requires editing three separate locations in one class.
- Several methods violate the contracts declared by their type signatures or names, producing surprising behavior at call sites.
- Workflow scheduling decorators are fused to business methods, preventing unit tests from running without workflow-engine infrastructure.
- Global mutable state is reached directly from the class, so tests cannot substitute it without monkey-patching.
- Real-remote integration test coverage is limited to a single branch-deletion scenario, leaving authentication, push, merge-conflict, and read-only flows untested against a real Git server despite the test infrastructure already supporting them.
- Type-checker suppressions are necessary to keep the module passing checks: per-module mypy overrides disable a set of error codes for `infrahub.git.base` and `infrahub.git.repository`, and a per-package ty override silences a set of diagnostic rules for `backend/infrahub/git/**`. Both blocks already carry a comment in `pyproject.toml` stating that they exist as a temporary measure and should be reactivated one rule at a time as the code improves. Today nothing forces that to happen.

This specification covers the **structural** improvement of the module. It is explicitly *not* a behavioral change. No user-facing feature is being added or removed.

The type-checker suppression list is a related but separate problem. The goal of this work is *not* to fix every suppressed violation. The goal is to put the module in a state where the remaining violations can be addressed one rule at a time — by tightening contracts, defining protocols, and shrinking the classes that those suppressions cover. Some suppressions will naturally become removable as a side-effect of the restructuring; those are removed opportunistically in the pull request that obsoletes them. The rest stay, documented in `pyproject.toml`, until follow-up work addresses them.

## Guiding Constraints *(mandatory)*

The following constraints apply to every user story in this spec and override any conflicting interpretation:

1. **Behavior preservation.** No observable behavior of any public method changes. Methods continue to produce the same return values for the same inputs, raise the same exceptions, and have the same side effects. Type annotations may be tightened to match what the code already does.
2. **No public API breakage.** All names currently exported from `infrahub.git.repository`, `infrahub.git.base`, `infrahub.git.integrator`, `infrahub.git.tasks`, `infrahub.git.models`, and `infrahub.git.utils` continue to be importable with the same names and signatures after every increment. Internal-only modules may be reorganized freely.
3. **One concern per pull request.** A pull request introduces at most one collaborator boundary, moves at most one method to a collaborator, fixes at most one correctness contract, registers at most one new protocol, or adds tests for one scenario family. Larger scopes are split. Reviewers can hold the entire change in their head.
4. **Delegate-then-remove for moves.** When a method is moved out of its current class to a collaborator, the original location retains a delegate so callers continue to work unchanged. The delegate body is exactly one expression — a call to the collaborator's corresponding method, optionally prefixed by `return` or `await`. The delegate is removed only in a final "cleanup" pull request that ships after all callers in the codebase have migrated to the new location. See FR-016 for the full rule.
5. **Independent revertability.** Every pull request in this series is mergeable on its own *and* revertable on its own. Reverting any single merged pull request leaves the codebase in a working, deployable state. No pull request relies on a later one to compile, pass tests, or behave correctly.
6. **Tests first where behavior is at risk.** Any pull request that touches code with thin coverage first lands the tests that pin the current behavior. The expanded real-remote integration suite is a prerequisite for the structural pull requests, not a follow-up.
7. **Additive before subtractive.** New abstractions (protocols, collaborator classes, plain implementations) are introduced alongside existing code first. Old code is removed only after all callers have migrated and tests pass.
8. **No new dependencies and no schema/migration changes.** This is pure internal restructuring.
9. **No growth in the type-checker suppression footprint.** Across any pull request in this work, the union of suppressed `(module-pattern, error-code)` cells affecting `infrahub.git` — counted across the mypy `disable_error_code` entries and the ty rule overrides in `pyproject.toml`, plus any inline `# type: ignore` (or equivalent) in source — never grows. A pull request that obsoletes an existing suppression removes it (or narrows its scope) in the same change. When code is moved to a new module path and an existing suppression must follow it, the source module's entry is correspondingly narrowed or removed in the same pull request, so the union does not grow — the diff shows one line added and one line removed, not just an addition. Inline `# type: ignore` is not introduced; any suppression that remains keeps its justification in the `pyproject.toml` override block.
10. **Opportunistic mock removal.** When a structural change in a pull request makes an existing test mock unnecessary — because a dependency is now injectable, because a collaborator is now testable against a protocol-based fake, or because workflow-engine initialization is no longer required — the test is rewritten in the same pull request to not use the mock. When the mock is still required, the test is rewired to the new path per FR-020. This is a side-effect of the refactor, not a goal of it; mocks that remain after the work are left alone here and handled by a follow-up.

## Story Dependencies

Stories are independently shippable in the sense that each delivers value on its own, but some sequencing constraints apply:

| Story | Depends on | Why |
|---|---|---|
| 1 — Safety-net tests | — | Prerequisite for every structural change. |
| 2 — Contract fixes | 1 (only for the read-only commit-value pinning test) | Annotation/registry changes are otherwise standalone. |
| 3 — Protocols | — | Purely additive; can land in parallel with 1 and 2. |
| 4 — File-importer extraction | 1, 3 | Needs the safety net for behavior parity and the protocol so the collaborator can depend on an abstraction. |
| 5 — Workflow decoupling | 1 | Needs the safety net; otherwise independent of the others. |
| 6 — Substitutable globals | 3 | Constructor changes should land against the stable protocol surface, not the concrete classes. |

## User Scenarios & Testing *(mandatory)*

The "users" of this specification are the backend developers and SREs who maintain `infrahub.git`. Each story is independently shippable and delivers value on its own.

### User Story 1 — Verifiable behavior under real Git failure conditions (Priority: P1)

As a backend developer about to refactor the Git module, I need a verifiable safety net that exercises real Git failure paths against a real remote, so that any subsequent refactor that breaks behavior is caught by a test rather than by a production incident.

**Why this priority**: Every later story depends on this one. Without behavior-pinning tests against a real remote, structural changes cannot be made safely. The test infrastructure to do this already exists; the gap is solely in what is tested.

**Pull-request shape**: One pull request per scenario family. Each family is small, reviewable, and lands on its own. Six families:

1. **Authentication and access** — wrong credentials, user without write access.
2. **Push failures** — non-fast-forward rejection, protected-branch rejection.
3. **Merge scenarios** — real conflicting changes in a file, merge with a commit that does not exist locally.
4. **Read-only repository against the real Git server** — sync with branch churn (gained and deleted branches), tag-based ref checkout (existing / missing / deleted), `update_latest_commit` where the remote has been force-pushed and the previously-known commit no longer exists.
5. **Repository setup** — `new()` against a reachable URL where the repository does not exist (404), clone of an empty repository.
6. **Sync with branch-state mismatches** — `sync()` where remote commits conflict with a populated local worktree (in addition to the new/deleted-branch cases in family 4).

**Independent Test**: Run the integration test suite against the real Git server fixture. The suite covers the six families above. All scenarios pass against the current implementation, establishing the behavior contract for the subsequent refactor.

**Acceptance Scenarios**:

1. **Given** a repository configured with invalid credentials, **When** a clone is attempted against the real Git server, **Then** the appropriate typed credential error is raised (not a generic Git command error) and the error message is preserved.
2. **Given** a repository configured with a user that has no write access, **When** a push is attempted, **Then** the typed access-denied error is raised and the error message preserves the remote's response.
3. **Given** a local branch that has diverged from its remote, **When** a push is attempted without force, **Then** the push is rejected and the typed error reflects the non-fast-forward condition.
4. **Given** a remote branch that has been marked protected, **When** a push is attempted, **Then** the typed protection-rejection error is raised.
5. **Given** two branches with real conflicting changes to the same file, **When** a merge is performed, **Then** the merge fails with the documented error contract (no mock or string-pattern shortcut is involved).
6. **Given** a merge that names a commit that does not exist in the local repository, **When** the merge is attempted, **Then** the typed missing-commit error is raised.
7. **Given** a read-only repository synced against the real Git server, **When** a new branch appears remotely, **Then** the next sync surfaces it; **When** a branch is deleted remotely, **Then** the next sync surfaces the deletion.
8. **Given** a read-only repository pinned to a tag, **When** the tag exists, **Then** checkout succeeds; **When** the tag does not exist, **Then** the typed missing-ref error is raised; **When** the tag is deleted remotely after a sync, **Then** the next sync surfaces the deletion with the documented contract.
9. **Given** a repository whose previously-known commit has been removed by a remote force-push, **When** `update_latest_commit` runs, **Then** the documented contract is observed (whether that is recovery to the new tip or a typed error reflecting the missing commit, the test pins what the current implementation does).
10. **Given** a reachable Git server URL where no repository exists at the given path, **When** `new()` is invoked, **Then** the typed not-found error is raised (not a generic Git command error).
11. **Given** a repository with no commits, **When** it is cloned, **Then** the clone succeeds (or the documented error contract is observed) and the subsequent sync does not raise an uncaught exception.
12. **Given** a populated local worktree and a remote that has accumulated commits conflicting with files in the worktree, **When** `sync()` runs, **Then** the documented contract is observed.

**Note on harder scenarios.** Additional scenarios identified in the original failure-coverage analysis — token expiry or revocation mid-operation, connection drops mid-fetch, server 5xx responses, timeouts on a large clone — require network manipulation (a proxy that injects faults) or fixture extensions beyond what the current Gogs fixture supports. They are not in this Story's minimum. If fixture work is undertaken to enable them, they are added as additional scenario families in further pull requests of the same shape.

---

### User Story 2 — Correctness fixes that match code to its declared contract (Priority: P1)

As a developer reading code in this module, I need method signatures and method names to match what the methods actually do, so that callers can rely on them without reading the implementation.

**Why this priority**: These are bugs in the type-level contract, not refactors. They mislead every caller. They can be corrected without any structural change and without altering runtime behavior — the runtime is already what the code does; only the declared contract is wrong.

**Pull-request shape**: One pull request per fix — the merge return-type annotation, the read-only commit-value contract clarification (with its pinning test), and the error-pattern registry. Three pull requests total.

**Independent Test**: A reader of the public signature can predict the runtime behavior. Specifically: the merge operation's return type annotation matches the value it actually returns; the read-only repository's "get commit value" method documents (or its name reflects) that it performs network I/O; the static error-mapping helper accepts new error patterns without being modified.

**Acceptance Scenarios**:

1. **Given** the merge operation, **When** the public signature is inspected, **Then** the declared return type matches the values actually returned on both success and early-exit paths.
2. **Given** the read-only repository's commit-value accessor, **When** a developer reads it, **Then** the network-fetch behavior is explicit (either via an unambiguous name, an explicit docstring contract, or both) and a pinning test verifies that the network call always occurs — the test MUST assert the call count of the remote fetch (one per invocation), not merely that the method returns successfully.
3. **Given** the static error-pattern-to-typed-exception mapping, **When** a new error pattern needs to be recognized, **Then** the new pattern can be registered by adding to a data structure rather than editing a conditional chain.

---

### User Story 3 — Stable abstraction boundary for repository consumers (Priority: P2)

As a developer of code that consumes a repository object (for read or for read/write), I need to depend on an interface rather than on a concrete class, so that my code, and its tests, are not coupled to the full surface area of the implementation.

**Why this priority**: Protocols are a purely additive change with zero behavioral risk. They become the stable boundary that subsequent extraction work can rely on. They also allow consumers that only need a subset of capabilities to express that at the type level.

**Pull-request shape**: One pull request to introduce the protocol module and its exports; one or more follow-up pull requests — one per caller — to migrate existing consumers to depend on the protocol. The protocol pull request is mergeable and useful on its own even if no caller is migrated. Two or more pull requests total.

**Independent Test**: Two protocol types are defined (one for the read-only capability set, one for the full read/write set) and re-exported from the existing repository module. At least one existing caller in the backend that today receives the union of the two concrete classes is updated to type its parameter against the protocol instead, and tests still pass.

**Acceptance Scenarios**:

1. **Given** a developer writing a new consumer that only reads files at a commit, **When** they look for a type to annotate their input with, **Then** a read-only protocol is available that exposes only the read-side capabilities.
2. **Given** a developer writing a consumer that needs full read/write access, **When** they annotate against the full protocol, **Then** both concrete implementations satisfy it.
3. **Given** the existing public exports of the repository module, **When** the protocols are introduced, **Then** no existing import is broken.

---

### User Story 4 — Separable file-import responsibility (Priority: P2)

As a developer adding support for a new repository-defined object type (a future "policy", "dashboard", or "generator-variant"), I need to add it in one place without editing the large integrator class, so that the change is reviewable in isolation and doesn't risk side effects on unrelated object types.

**Why this priority**: The single largest source of size and coupling in the module is the file-import responsibility being fused to the lifecycle responsibility on one class. Extracting an importer collaborator — built on top of the protocols from Story 3 — is the highest-leverage SRP/OCP improvement available and unlocks per-type evolution.

**Pull-request shape**: One pull request to introduce the empty `RepositoryFileImporter` collaborator and wire it into the integrator's constructor. Then one pull request per importable object type that moves its `import_*` lifecycle (with its compare / create / update helpers) to the collaborator, leaving a one-line delegate on the integrator. A final cleanup pull request removes the delegates once all callers have migrated. Approximately one plus N plus one pull requests, where N is the number of object types — each pull request small, reviewable, and revertable in isolation.

**Independent Test**: A new `RepositoryFileImporter` collaborator exists. At least one (and ideally all) of the existing `import_*` flows is implemented by the collaborator. The integrator class still exposes the same method names, but each one delegates to the collaborator. Adding a new object type can be done by registering a handler with the importer; no edit to the integrator's orchestration is required.

**Acceptance Scenarios**:

1. **Given** the current set of importable object types, **When** the importer collaborator is introduced and the existing methods delegate to it, **Then** the full integration test suite continues to pass.
2. **Given** the integrator class after extraction, **When** a developer reads it, **Then** it no longer owns both orchestration and per-type lifecycle logic — its remaining responsibility is nameable in a single skim.
3. **Given** a hypothetical new object type, **When** a developer adds support for it, **Then** they do so by registering a handler with the importer rather than by editing the integrator's main flow.

---

### User Story 5 — Domain logic that runs without the workflow engine (Priority: P2)

As a developer writing or running a unit test against repository business logic, I need to invoke that logic without standing up the workflow engine, so that tests are fast, deterministic, and independent of external orchestration.

**Why this priority**: Workflow decorators on business methods are the single largest source of test friction in this module. Splitting decorated wrappers from plain async implementations is a mechanical, low-risk change with immediate testability payoff. It also clarifies the boundary between "what the class does" and "what the workflow does".

**Pull-request shape**: One pull request per workflow-decorated method. Each pull request extracts that method's body into a plain async implementation, moves the decorated entry point to the workflow module, and adds at least one unit test exercising the implementation directly without workflow-engine initialization. Approximately one pull request per decorated method.

**Independent Test**: For every business method currently decorated as a workflow flow or task on the integrator class, a plain async implementation exists and is what the class method calls. The workflow-decorated entry point lives in the workflow module and delegates to the implementation. A unit test can exercise the implementation directly without initializing the workflow engine.

**Acceptance Scenarios**:

1. **Given** an existing workflow-decorated method on the integrator, **When** the split is performed, **Then** the public method name and signature are unchanged and the workflow-decorated entry point in the workflow module continues to be invoked by its existing callers.
2. **Given** a unit test for the business logic, **When** it is run, **Then** it does not require workflow-engine initialization.
3. **Given** the existing workflow flows defined elsewhere, **When** they are inspected, **Then** they call the plain implementation rather than duplicating its logic.

---

### User Story 6 — Substitutable global dependencies (Priority: P3)

As a developer writing tests for repository behavior, I need to be able to supply the dependencies the class needs (default branch name, SDK client) at construction time, so that I don't have to monkey-patch global singletons.

**Why this priority**: This unlocks cleaner tests but is gated on Stories 3–5 being in place. Doing it earlier would risk a wider blast radius. The optional-injection approach makes it backwards compatible.

**Pull-request shape**: One pull request for the optional default-branch constructor parameter (with a falls-back-to-the-global default). One pull request for the SDK-client initialization move out of the property accessor. Two pull requests total.

**Independent Test**: The base class accepts an optional default-branch override at construction time (falling back to the existing global when omitted). The SDK client is initialized in a way that does not mutate model state from inside a property accessor. Existing tests continue to pass; at least one new test exercises injection without patching globals.

**Acceptance Scenarios**:

1. **Given** a test that needs a non-default branch name, **When** it constructs a repository, **Then** it can pass the branch name directly without touching any global.
2. **Given** a freshly constructed repository, **When** the SDK client accessor is read twice, **Then** the object's internal state is not mutated by the read.
3. **Given** any existing caller, **When** the constructor change ships, **Then** the call site still compiles and behaves identically.

---

### Edge Cases

- A merged pull request needs to be reverted: because every pull request is independently revertable, the in-between state remains green. The acceptance criterion is that the full backend test suite and the expanded integration suite both pass with the revert applied.
- A consumer outside the backend (for example, a script, the SDK, or generated code) imports a symbol from the module: any symbol currently re-exported from `infrahub.git.repository` (the most heavily imported entry point) is preserved by name. If a rename is desirable, the old name is kept as an alias for the duration of this work.
- The real Git server fixture is unavailable in CI for a particular run: the integration tests are allowed to be skipped with a clear marker, but they must run by default in the CI configuration that gates merges to the development branch.
- The expanded test suite reveals a pre-existing bug: it is documented and tracked separately. This specification does not attempt to fix latent behavioral bugs — it pins the current behavior and restructures. The pinning test still lands, asserting the current (incorrect) behavior, with a comment in the test body or a `pytest.mark` flag that names the tracking ticket. When the separate behavioral-fix ticket lands, it updates the assertion in the same pull request that changes the behavior. Behavioral fixes are out of scope here so that the restructuring remains reviewable.
- A pull request that moves a method to a collaborator lands, but a follow-up pull request that migrates the last remaining caller never lands: the delegate stays. This is acceptable — the codebase is in a working state. The cleanup pull request that removes the delegate simply waits.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The expanded real-remote integration test suite MUST cover, as a minimum, the six scenario families enumerated in Story 1's pull-request shape: authentication and access (wrong credentials, no-write-access user); push failures (non-fast-forward, protected branch); merge scenarios (real conflicting changes, merge with a commit not present locally); read-only repository against the real Git server (sync with branch churn, tag-based ref checkout for existing / missing / deleted tags, `update_latest_commit` with a force-pushed previously-known commit no longer present); repository setup (`new()` against a reachable URL with no repository / 404, clone of an empty repository); and sync with branch-state mismatches (remote commits conflicting with a populated local worktree). Additional fault-injection scenarios (token revocation mid-operation, mid-fetch connection drops, 5xx responses, large-clone timeouts) MAY be added in further pull requests of the same shape if fixture extension is undertaken; they are not blockers for this Story.
- **FR-002**: The expanded integration test suite MUST be enabled in the CI configuration that gates merges to the development branch.
- **FR-003**: The merge operation's declared return type MUST match the values it actually returns. The fix is a type-annotation correction, not a behavioral change.
- **FR-004**: The read-only repository's commit-value accessor MUST make its network behavior explicit — either by name, by a documented contract on the method, or both — and a regression test MUST pin that the network call occurs.
- **FR-005**: The static error-pattern-to-typed-exception mapping in the base class MUST be expressible as data (an ordered registry of `(pattern, exception_factory)` entries) rather than a chain of conditional branches. Adding a new pattern MUST NOT require editing a function body.
- **FR-006**: A read-only protocol type and a full repository protocol type MUST be defined in the module and re-exported from the existing repository module's public surface. They MUST describe only the methods their respective consumers need.
- **FR-007**: A `RepositoryFileImporter` collaborator MUST exist and own the per-type import lifecycle for at least one object type initially, with the existing integrator method delegating to it. The collaborator MUST be designed so that additional object types are added by registering a handler with it.
- **FR-008**: For each workflow-decorated method on the integrator class, a plain async implementation MUST exist, and the workflow-decorated entry point MUST live in the workflow module and delegate to it. The public method name on the integrator MUST remain unchanged.
- **FR-009**: The base class MUST accept an optional default-branch override at construction time. When omitted, the existing global lookup MUST be used. No existing call site is required to change.
- **FR-010**: The SDK client MUST NOT be lazily initialized inside a property accessor that mutates the model's persisted fields. Initialization MUST occur via the standard model-construction lifecycle or an explicit configure call.
- **FR-011**: Every pull request in this work MUST be independently mergeable: the full backend test suite and the expanded integration suite MUST both pass at its tip.
- **FR-012**: Every pull request in this work MUST be independently revertable: reverting any single merged pull request MUST leave the codebase in a working, deployable state, with no later pull request relying on it to compile, pass tests, or behave correctly.
- **FR-013**: Every symbol currently importable from `infrahub.git.repository` MUST remain importable from the same path with the same name after every pull request.
- **FR-014**: No pull request in this work MUST change observable behavior of any public method. "Observable behavior" includes: return values, exception types, exception message strings, stack-trace module paths visible to error reporting or logging, and the names of loggers obtained via `logging.getLogger(__name__)` at any callsite that emits to a log. Type annotations and docstrings MAY be tightened only to reflect what the code already does. When a pull request moves code between modules in a way that changes a logger name, an exception's module path, or the traceback shape, the pull request description MUST call this out so that observability tooling (alerts, dashboards, Sentry-style grouping) can be updated in parallel.
- **FR-015**: No pull request in this work MUST introduce a new runtime dependency or change a database schema or persisted data structure.
- **FR-016**: When a method is moved from its current class to a collaborator, the original location MUST retain a delegate so call sites continue to work unchanged. The delegate body MUST be exactly one expression — a call to the collaborator's corresponding method, optionally prefixed by `return` or `await`. The delegate MUST contain no conditional, no loop, no transformation of arguments, and no transformation of the return value. The canonical implementation lives in the collaborator; the delegate is purely a call-forwarding shim. The delegate MUST be removed only in a dedicated, final cleanup pull request that ships after all callers have migrated to the new location.
- **FR-017**: Each pull request in this work MUST be small enough to be reviewed end-to-end in a single sitting and MUST address at most one concern: one collaborator boundary, one moved method, one correctness contract, one new protocol, or one scenario family of tests.
- **FR-018**: Across any pull request in this work, the union of suppressed `(module-pattern, error-code)` cells affecting `infrahub.git` MUST NOT grow. The union is counted across the mypy `disable_error_code` entries in `pyproject.toml`, the ty rule overrides in `pyproject.toml`, and any inline `# type: ignore` (or equivalent) markers in source.
- **FR-019**: When a pull request's restructuring makes an existing type-checker suppression unnecessary, the suppression MUST be removed (or its scope narrowed) in the same pull request. When a pull request moves code to a new module path and an existing suppression must follow it, the source module's entry MUST be correspondingly narrowed or removed in the same pull request — so that FR-018's union invariant holds. Suppressions that remain MUST keep their justification in the `pyproject.toml` override block, not in source-level comments. No new inline `# type: ignore` markers MUST be introduced.
- **FR-020**: Before any pull request that moves a method to a different class or module, the author MUST audit existing `unittest.mock.patch(...)` and `patch.object(...)` call sites in the test suite that reference the source path of the moved method. Affected tests MUST be updated in the same pull request to either patch the new path or to patch a stable seam that does not move (such as the integrator's delegate). This prevents tests from silently passing for the wrong reason after a move.
- **FR-021**: For each workflow-decorated method extracted in Story 5, the plain async implementation MUST be private to its module (named with a leading underscore or otherwise marked non-public). In-process callers — including recursive self-calls within the same class — MUST go through the workflow-decorated wrapper, not the plain implementation, so that retry, checkpointing, telemetry, and structured-logging behavior provided by the workflow engine is preserved. Any deviation from this rule MUST be justified in an Architecture Decision Record under `dev/adr/`.
- **FR-022**: When a pull request makes a test mock structurally unnecessary — because the dependency the mock was standing in for is now injectable, because the collaborator is now testable against a protocol-based fake, or because the workflow engine is no longer required — the affected test MUST be rewritten in the same pull request to no longer use that mock. Replacement choices: behavior-level tests SHOULD use the real Gogs fixture; unit-level tests SHOULD use a fake implementation of the relevant protocol. Mocks that are still required (for example, simulating network timeouts or third-party failures) MAY remain. A reviewer of a mock-removal change MUST confirm the new test exercises the same property the original mock was guarding.
- **FR-023**: At the close of every pull request in this work, no two locations in the codebase MUST contain divergent implementations of the same logical operation. The "delegate-with-one-expression-body" form of FR-016 satisfies this because a delegate has no logic of its own to diverge. If a future change needs to modify the behavior of a moved method, the change MUST happen in the collaborator's implementation and MUST NOT be applied to the delegate. The same rule applies if work pauses or is split across releases: a delegate that remains in place across releases is acceptable; two divergent implementations of the same method in two locations is not.

### Key Entities

- **Repository protocols**: Two protocol types defining the read-only and the full read/write capability sets. They are the stable interface that consumers and collaborators depend on instead of the concrete classes.
- **`RepositoryFileImporter`**: A collaborator class that owns the per-type import lifecycle (compare / create / update for each object type). It accepts a repository instance via its constructor and is composed into the integrator.
- **Error-pattern registry**: An ordered, data-defined mapping from a substring or regex pattern in a Git command's stderr to a typed exception class. Replaces the inline conditional chain.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer adding a new repository-defined object type can do so by changing one well-defined location (the importer registration) plus any new per-type handler, without editing the orchestration method in the integrator class.
- **SC-002**: Unit tests for any extracted business logic run without initializing the workflow engine and without monkey-patching global singletons.
- **SC-003**: The integrator class is materially clearer and easier to maintain after this work. Concretely: the responsibilities listed under SRP have been split into named collaborators; the integrator no longer owns both orchestration and per-type lifecycle logic; a developer reading the class can name its remaining responsibility in a single skim. Validation is by reviewer judgment at the close of Story 4 and again after the delegate-removal cleanup pull request. Any change in the class's line count is a side-effect indicator, not the success criterion.
- **SC-004**: Every public-facing import path used elsewhere in the codebase resolves identically before and after each pull request — verified by a static check that compares the set of names exported from the module's public modules before and after.
- **SC-005**: The integration test suite running against the real Git server covers the six scenario families enumerated in FR-001 (authentication and access; push failures; merge scenarios; read-only repository against the real Git server; repository setup; sync with branch-state mismatches) and runs by default on the merge-gate CI configuration.
- **SC-006**: The merge operation's declared return type and the read-only commit-value accessor's contract are accurate enough that a developer can rely on the public signature alone, verified by removing the existing `isinstance` checks at call sites where they are now redundant — or, if any remain, explaining why in code review.
- **SC-007**: A new typed exception can be added to the error-pattern registry by adding a single entry to a data structure, with no edit to a function body and no change to control flow.
- **SC-008**: Each pull request in this work is reviewable end-to-end in a single sitting (a reviewer can hold the full change in their head) and each one can be reverted on its own without breaking the codebase. A spot check at the close of each story confirms both.
- **SC-009**: At the close of this work, each type-checker suppression that remains in the `pyproject.toml` override blocks affecting `infrahub.git` is scoped tightly enough that it can be reactivated by a small, focused follow-up change — the structural conditions for incremental hardening exist. No new suppressions affecting the module have been added; no per-source-file `# type: ignore` lines have been introduced; suppressions that remain stay grouped in the existing override blocks under the "should be reactivated one by one" comment header. Whether the count of remaining suppressions is lower than the starting state is a side-effect indicator, not the success criterion.
- **SC-010**: At the close of this work, each mock that remains in the affected test suites (`backend/tests/unit/git/`, `backend/tests/integration/git/`, and any other test file that imports from `infrahub.git`) is either clearly intentional or clearly a candidate for follow-up replacement — a developer reading the test can tell which without guessing. A brief audit document attached to the Jira epic enumerates the residue and the category for each remaining mock. The audit document is the deliverable; carrying out the follow-up replacements is not in scope.

## Assumptions

- The existing real-remote test fixture (a real Git server started in a container, with a known admin token and a helper to create repositories) is suitable as-is for the expanded scenarios. It already starts, installs, creates an admin user, and yields a token; only new test cases are needed on top of it.
- The development branch (`develop`) is the default merge target for every pull request in this work. Each pull request is merged on its own; no long-lived integration branch is created.
- The user-facing behavior of repositories that consume this module (the UI, the SDK, repository-defined Python checks and transforms) is out of scope and is not being changed.
- The Jira epic IFC-2533 ("SOLID refactoring for infrahub.git module") is the parent for implementation work derived from this specification.
- The expanded integration suite is permitted to slow down CI by an amount commensurate with the value of the coverage. If the runtime becomes a problem, the scenarios are parallelizable across separate test sessions; this optimization is a follow-up, not a prerequisite.
- Towncrier changelog fragments are produced once, at the close of this work, summarizing the structural change for release notes. Individual pull requests do not each ship a fragment.
- No detectable performance regression is expected from the added indirection. Each collaborator hop is a single attribute lookup and function call — sub-microsecond on the path being refactored. If a regression is observed during the work, it is investigated and either fixed or documented before the next pull request lands.

## Out of Scope

- Splitting the base class itself, or changing factory preconditions on `new()`. These would require coordinated changes across many call sites and are deferred until protocols are established and consumers have migrated to them. Note that renaming the read-only repository's commit-value accessor *is* in scope per FR-004 (one of the permitted ways to make its network behavior explicit), provided the rename does not break the abstract contract declared on the base class.
- Touching the cached factory that returns initialized repository instances. Its import surface is the widest in the module and the most call-site-variant; it is left alone for this work.
- Any behavioral fix discovered while writing the safety-net tests. Such issues are documented and tracked separately so that this work remains a pure structural refactor.
- Documentation updates beyond what is needed to describe the new collaborators and protocols, and any docstring clarifications required by FR-004.
- Resolving every type-checker violation currently suppressed for `infrahub.git`. This work removes the suppressions that the restructuring obsoletes and forbids new ones, but the remaining violations — those that require runtime changes to satisfy the checker, or that are out of scope for this refactor — are left in the override blocks for a follow-up. The goal is to reach a state where each remaining suppression can be reactivated by a small, focused change.
- Comprehensive removal of mocks from the affected test suites. This work removes mocks that the restructuring makes structurally unnecessary (FR-022) and enumerates the residue (SC-010), but does not aim to eliminate every mock. Mocks that are still appropriate (for example, simulating transient network or third-party failures) remain; the rest are left to a follow-up informed by the closing audit.
