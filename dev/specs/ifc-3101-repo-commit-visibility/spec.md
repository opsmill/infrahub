# Feature Specification: Git Repository Commit Visibility

**Feature Branch**: `pog-repo-commit-visibility-ifc-3101`
**Created**: 2026-09-03
**Status**: Approved
**Jira**: Epic [IFC-3101](https://opsmill.atlassian.net/browse/IFC-3101), first slice of [INFP-671](https://opsmill.atlassian.net/browse/INFP-671) (Git repository sync visibility)
**Source PRD**: [PRD: Git repository commit visibility](https://opsmill.atlassian.net/wiki/spaces/Product/pages/858816518/PRD+Git+repository+commit+visibility)
**Sibling**: [IFC-3104](https://opsmill.atlassian.net/browse/IFC-3104) / [PRD: Cross-branch repository status query](https://opsmill.atlassian.net/wiki/spaces/Product/pages/865894402), which owns the branch rows that this feature's P3 annotates
**Frontend design**: [Git sync visibility canvas](https://claude.ai/design/p/d8efb789-c722-4622-b8d8-0bceb7054774?file=Git+sync+visibility.dc.html&via=share)
**Input**: User description: "The specifications are available here: https://opsmill.atlassian.net/wiki/spaces/Product/pages/858816518/PRD+Git+repository+commit+visibility"

## Problem

When a user pushes a commit to a repository connected to Infrahub, nothing in the product tells them whether it was picked up. The repository page reports an "in sync" status that reflects only the default branch, and finding the commit Infrahub is actually running means copying hashes and comparing them by hand. A branch imported from Git presents as having no relationship with Git at all.

For read-only repositories the situation is worse. Infrahub never looks at the remote unless something changes on the Infrahub side, so a tracked ref can advance or be rewritten entirely without a trace.

The information exists, but not in Infrahub. Answering any question about what Infrahub is running means leaving the product for the git remote, comparing hashes by hand, and in the harder cases asking someone with access to worker logs. Failures are noticed late, usually because data looks stale rather than because anything reported a problem, and diagnosis then falls to the Solution Architecture team at roughly two hours per incident.

This is not only a troubleshooting gap. Seeing a repository's recent commits, who wrote them and when, is ordinary information a user should be able to read from the repository they are looking at, whether or not anything is wrong.

## Solution Summary

A repository gains a commit view showing recent commits for the Infrahub branch the user is on: hash, message, author and date, newest first. That list is useful on its own, as the repository's history read from inside Infrahub. Two markers then answer the question that brings most people to it: which commit Infrahub has imported, and which commit is at the head of the remote branch or tracked ref. The commits between them are what is waiting to be imported. The repository's branch list gains the latest remote commit for any branch that has drifted from what Infrahub tracks.

Where the tracked ref has been rebased or force-pushed, that is reported as its own condition rather than being flattened into "behind", because the commit Infrahub is running no longer belongs to the ref's history at all.

Read-only repositories gain a slow background check that notices upstream movement. It looks and never touches: it cannot advance the tracked commit, cannot trigger an import, and cannot change which commit Infrahub is running.

Commits are read live from Git at request time. They are never stored as Infrahub objects, so they never appear in a data diff, never participate in a merge, and adding a repository costs nothing per commit.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See what Infrahub has imported and what is pending, on the current branch (Priority: P1)

A developer pushes a commit to a connected repository, opens the repository in Infrahub on the branch they are working on, and opens the commit view. They see recent commits newest-first with the remote head and the imported commit both marked. The commits between the two markers are identifiable as pending import. They can copy a hash out of the list, see who authored each commit and when, and see how fresh the information is.

If the tracked ref has been rebased or force-pushed so the imported commit is no longer part of its history, the view says so explicitly instead of presenting the imported commit as an earlier point on the current history.

If no worker has a local copy of the repository yet, the view shows an explicit not-yet-available state, a warm-up starts on its own, and the view resolves without the user doing anything once a copy exists.

**Why this priority**: It puts the repository's history in the product. That answers "has my commit been imported" directly, and it also gives a user the commits, authors and dates they would otherwise leave Infrahub to read. It delivers the whole value for read-write repositories on its own.

**Independent Test**: Against a fixture repository whose remote has advanced past the commit Infrahub imported, open the commit view on that branch and confirm both markers, the pending range, the per-commit fields, and the freshness statement. No read-only repository and no branch list is required.

**Acceptance Scenarios**:

1. **Given** a read-write repository whose branch has imported an older commit while the remote branch head has advanced, **When** the user opens the commit view on that branch, **Then** the log lists commits newest-first with hash, message, author and date, the remote head is marked, the imported commit is marked, and the commits between them are identifiable as pending import.
2. **Given** a read-only repository tracking a ref whose head has moved beyond the imported commit, and the background check has run since, **When** the user opens the commit view, **Then** the log is that of the tracked ref, the ref head and the imported commit are both marked, and the gap between them is visible.
3. **Given** a read-only repository whose tracked ref has been rebased and force-pushed so the imported commit is no longer part of its history, **When** the user opens the commit view, **Then** the repository is reported as having a rewritten ref rather than as being behind, no pending count is presented, and the imported commit is not shown as an earlier point on the current history.
4. **Given** a repository whose remote head equals the imported commit, **When** the user opens the commit view, **Then** both markers sit on the same commit and nothing is identified as pending.
5. **Given** a repository no worker has cloned, **When** the user opens the commit view, **Then** an explicit not-yet-available state is shown rather than a generic error, a warm-up is triggered, and the view resolves without user action once a worker holds a copy.
6. **Given** a repository with a long history, **When** the user opens the commit view, **Then** the first page appears promptly and the user can page through older commits.
7. **Given** a commit in the list, **When** the user copies its hash, **Then** the full hash is placed on the clipboard without transcription.
8. **Given** a user who can view the repository, **When** they open the commit view, **Then** it loads. **Given** a user who cannot view the repository, **When** they attempt the same, **Then** they are denied by the same rule that already denies the repository itself.
9. **Given** the user switches Infrahub branch, **When** the commit view is shown, **Then** the log, markers and pending range reflect the newly selected branch.

---

### User Story 2 - Notice upstream movement on a read-only repository without being asked (Priority: P2)

An operator runs a read-only repository pinned to a tag or branch. Someone pushes to that tracked ref. Within the configured interval, and with no action from the operator, Infrahub notices the movement and reflects it in the commit view. What Infrahub is actually running does not change: the tracked commit stays where it is, no import runs, and no worker checks out anything new. The operator can also trigger the check on demand after pushing a tag instead of waiting out the interval.

**Why this priority**: Without it, User Story 1 is blind for read-only repositories, which are exactly the case where Infrahub today never looks at the remote. It ships and demos independently: advancing a fixture remote and observing the drift appear is a complete demonstration.

**Independent Test**: Advance a fixture read-only remote, wait out the interval (or trigger the check), and confirm the drift is visible, the tracked commit and imported content are unchanged, and the convergence request went to the whole worker pool with the tracked commit pinned. No commit view UI is required; the reported values suffice.

**Acceptance Scenarios**:

1. **Given** a read-only repository whose tracked ref has advanced upstream, **When** the background check runs, **Then** every worker's local copy reflects the new ref head, the drift is visible in the product, and the repository's tracked commit and imported content are unchanged.
2. **Given** a read-only repository whose tracked ref has advanced upstream, **When** the operator triggers the check on demand, **Then** the drift is visible without waiting for the interval.
3. **Given** a read-only repository whose tracked ref has not moved, **When** the background check runs, **Then** it does not transfer repository content and changes nothing.
4. **Given** a read-only repository whose tag was moved upstream so the previously tracked commit is no longer referenced by that tag, **When** the check runs, **Then** the imported commit's content remains readable on every worker.
5. **Given** the check and an import are due at the same time for the same repository, **When** both run, **Then** they execute one after the other rather than interleaving, and repeated check runs do not queue up behind one another.
6. **Given** a platform administrator changes the check interval, **When** the new value takes effect, **Then** subsequent checks follow the new interval.

---

### User Story 3 - See per-branch drift from the branch list (Priority: P3)

An operator opens a repository's branch list and sees, for each branch, the commit Infrahub tracks. Any branch whose remote has moved on also shows the latest remote commit, so the operator can spot the branch that is behind without opening each one. If the git-derived information cannot be produced at that moment, the branch rows still appear and only the drift column reports its own unavailable state.

**Why this priority**: It extends the finding of drift from one branch at a time to all branches at once. It depends on the Branches card delivered by the sibling PRD for the rows it annotates, and it is the least urgent of the three because User Story 1 already answers the question for the branch the user is on.

**Independent Test**: Against a repository with many branches, three of which are behind, open the branch list and confirm the three show a remote commit differing from the tracked one, the rest do not, and the page loads with one worker request and a branch-count-independent number of database queries for the drift information.

**Acceptance Scenarios**:

1. **Given** a repository with 200 branches, 3 of which are behind their remote, **When** the user opens the branch list, **Then** each branch shows Infrahub's tracked commit, the 3 behind also show the latest remote commit, and the drift information for all branches is retrieved together rather than one branch at a time, on both the Infrahub side and the Git side.
2. **Given** no worker is able to answer, **When** the user opens the branch list, **Then** the branch rows render with their Infrahub-side values and the drift column alone reports that it is unavailable.
3. **Given** a branch that exists in Infrahub but has no counterpart on the remote, **When** the user opens the branch list, **Then** that branch shows no remote commit and is not reported as drifted.
4. **Given** a read-write repository with a branch that is not synchronised with Git, **When** the user opens the branch list, **Then** that branch is absent from the list, matching the row set of the Branches card, because a mismatch there would mean the branch needs rebasing rather than that an import failed.
5. **Given** a read-only repository whose branches have not each pinned their own ref, **When** the user opens the branch list, **Then** every branch appears with the tracked commit and ref that its own branch resolves, and a branch with nothing imported anywhere is reported as not tracked rather than as drifted.

---

### Edge Cases

- **Repository with no commits.** The tracked commit is optional; the log is empty and there is no imported commit to mark.
- **Tracked ref rebased or force-pushed.** The imported commit is no longer an ancestor of the head. Reported as rewritten, never as behind, and never with a pending count that would be meaningless.
- **Imported commit no longer reachable on the remote at all.** A stronger form of the above; the marker has nowhere to sit. Reported as its own condition, orphaned, and determined before any ancestry test, because asking whether an unresolvable hash is an ancestor fails rather than answering no (FR-006).
- **Non-linear history.** Merge commits break any assumption that everything below the imported marker was imported, which is why per-commit state is delivered by the system rather than inferred from list position.
- **Tag moved upstream while a worker has the old commit checked out.** Updating the tag must not leave the imported commit unreachable.
- **A worker misses a convergence notification** (restarting, or down at the time) and serves older data than its peers until the next movement. Covered by the freshness statement rather than by guaranteeing delivery.
- **Freshly scaled-up worker, idle repository.** Convergence is movement-driven, so a new worker can stay cold indefinitely for a repository with no upstream activity until a read triggers a warm-up.
- **Branch present in Infrahub with no remote counterpart** (created before the repository was added). No remote head exists to compare against.
- **Branch not synchronised with Git.** On a read-write repository the branch is not part of the branch list's row set at all. A mismatch there would legitimately mean the branch needs rebasing, not that an import failed. The commit view needs the same rule for the same reason: such a branch may still share a name with a real remote branch, and mapping it through unconditionally would report it as behind when Infrahub deliberately never imports it. It is reported as not tracked, not as drifted, on both surfaces (FR-006, FR-021).
- **Branch that has never imported.** Its tracked commit is the value its origin branch held at the fork point, which is the commit that branch genuinely runs. Not an error state, and not reported as drift on its own.
- **Remote refs check fails for one repository** (authentication rejected, DNS failure, remote deleted, remote hanging). Recorded with the repository and the reason, the cycle continues with the other repositories, and the failed repository is retried on the next cycle rather than being treated as checked. A repository failing every cycle keeps reporting its last known state with an unchanged freshness stamp, which is the signal that something is wrong.
- **Staleness.** The log reflects the last time a worker updated its local copy, not the remote right now. Bounded by the relevant interval per repository kind, and stated rather than implied to be live.
- **Very long history and very many branches.** Paging is mandatory and no total is offered at all (FR-024); drift for all branches is produced together regardless of branch count.
- **Concurrent first reads of an uncloned repository.** Every read returns promptly with the not-yet-available state and exactly one warm-up starts.
- **No worker available or worker too slow.** The request returns within a bounded time with a recognisable error that tells the caller when to retry, rather than hanging.
- **The drift column is unavailable while the branch rows are not.** The branch list renders the rows and reports the drift column's own state.

## Requirements *(mandatory)*

### Functional Requirements

#### Reading commits

- **FR-001**: System MUST return a paged commit log for a repository as seen from a given Infrahub branch, newest first, each entry carrying hash, message, author and date. _Verify_: query a fixture repository; assert ordering, field presence, and correct paging across a known history.
- **FR-002**: System MUST create no per-commit records. Adding a repository MUST add no data proportional to its commit count. _Verify_: add a repository with a multi-hundred-commit history; assert the stored data delta is independent of history length.
- **FR-003**: System MUST report, per Infrahub branch, both the commit it has imported and the latest commit available on the remote branch or tracked ref. _Verify_: advance a fixture remote without importing; assert both values are returned and differ.
- **FR-004**: System MUST produce the remote head for every branch of a repository in a single request to a worker, and MUST read Infrahub's per-branch tracked values in a number of database queries that does not grow with branch count. _Verify_: instrument worker requests and database queries; assert exactly one worker request, and an identical query count, for a repository with 5 and with 200 branches.
- **FR-005**: System MUST attach an explicit state to each returned commit (for example imported, pending, head) rather than requiring the consumer to infer it from position in the list. _Verify_: assert the state is populated for a non-linear history where position alone would be misleading.
- **FR-006**: System MUST distinguish a repository that is behind its remote from one whose remote history has been rewritten, determined by whether the imported commit is still an ancestor of the current head, and MUST report the number of pending commits only in the former case. It MUST further distinguish both from the case where the imported commit's object cannot be resolved at all, which is reported as its own orphaned condition and MUST be determined before any ancestry test is attempted, since an unresolvable hash makes that test fail rather than answer. _Verify_: rebase and force-push a fixture remote; assert the rewritten condition is reported and no pending count is presented. Separately, point the imported commit at a hash the clone does not hold; assert the orphaned condition is reported, no pending count is presented, and no error is raised.
- **FR-007**: System MUST convey how fresh the returned git data is, as the point in time the underlying local copy was last updated. For a read-only repository it MUST also convey when the remote was last checked for movement, because a repository whose remote has been quiet reports an old update time even though it was checked moments ago, and presenting only the latter would misrepresent it as stale. _Verify_: assert the response carries the update timestamp and that it changes after a fetch; separately assert that a read-only repository whose remote has not moved reports a recent check time after a check cycle, with the update time unchanged.
- **FR-008**: System MUST compute only what the caller selected: no worker request is made when no git-derived field is requested. _Verify_: instrument worker requests; assert zero for an Infrahub-side-only selection.
- **FR-009**: Users MUST be able to read a commit log for any repository they can already view, with no additional permission. _Verify_: a user with repository read access succeeds; a user without it is denied by the existing path.
- **FR-010**: Users MUST be able to copy a commit's full hash from the commit view. _Verify_: copy action places the full hash on the clipboard.
- **FR-011**: The commit view MUST follow the Infrahub branch the user is viewing, consistent with every other view in the product. _Verify_: switch branch and assert the log and markers change accordingly.

#### Availability of the read path

- **FR-012**: System MUST bound the time it waits for a worker and MUST return a catalogued error carrying a retry hint when that bound is exceeded. _Verify_: with no worker consuming, assert the request returns within the bound carrying the expected error code and retry hint.
- **FR-013**: System MUST NOT clone a repository synchronously within a read. When the answering worker holds no local copy it MUST report unavailable and trigger an asynchronous warm-up, collapsing concurrent triggers into one. _Verify_: issue concurrent reads against an uncloned repository; assert every read returns promptly and exactly one clone starts.
- **FR-014**: The commit view MUST present the not-yet-available state distinctly from an error and MUST resolve on its own once a local copy exists, without user action. _Verify_: open the view on an uncloned repository, wait for warm-up, assert the view populates without a manual refresh.

#### Keeping read-only repositories current

- **FR-015**: System MUST periodically check a read-only repository's remote for movement of its tracked refs, on a configurable interval, and MUST also expose that check on demand. _Verify_: advance a fixture remote, wait out the interval, and assert the movement is detected; separately assert the on-demand trigger detects it without waiting.
- **FR-016**: That check MUST NOT alter the tracked commit, MUST NOT trigger an import, and MUST NOT change which commit any worker has checked out. _Verify_: advance a fixture remote across several check cycles; assert the tracked commit and the imported content are byte-identical throughout.
- **FR-017**: When a tracked ref has moved, System MUST converge every worker's local copy, not only the copy on the worker that performed the check, and the convergence step MUST be subject to FR-016. _Verify_: assert the check broadcasts the convergence request to the whole worker pool with the tracked commit pinned, and that a worker receiving it updates its copy without moving the pin. Delivery to every worker is the existing broadcast's behaviour and is not re-verified per feature; the freshness statement covers a worker that misses one.
- **FR-018**: The check MUST inspect the remote's refs before transferring any content, so an idle repository costs a refs listing and nothing more. _Verify_: run the check against an unchanged remote and assert no content transfer.
- **FR-019**: Steps of the check that modify the local copy MUST NOT interleave with other git operations on it. Inspecting the remote's refs changes nothing locally and MUST NOT hold that exclusion, so a slow or unreachable remote cannot block an import. _Verify_: run the check concurrently with an import against the same repository and assert the modifying steps are serialised; assert that a check blocked on an unresponsive remote does not delay a concurrent import of the same repository.
- **FR-020**: Updating refs and tags during the check MUST NOT render the imported commit unreachable on any worker. _Verify_: move a tag upstream so the previously tracked commit is no longer referenced by it, run the check, then read the imported commit's content. One worker suffices: what protects the commit is its worktree acting as a reachability root, which is identical on every worker rather than a property of the fleet.

#### Per-branch drift on the branch list

- **FR-021**: The branch list MUST show, for each branch whose remote head differs from the commit Infrahub tracks, the latest remote commit. _Verify_: fixture with 200 branches, 3 behind; assert exactly those 3 carry a remote commit.
- **FR-022**: The branch rows MUST render when the git-derived drift information is unavailable, with the unavailable or timed-out state confined to the drift column. _Verify_: with no worker able to answer, assert the rows return and the column reports its own state.
- **FR-023**: Drift MUST be displayed, not filtered: the branch list does not offer filtering, ordering or counting by drift in this slice. _Verify_: assert no such filter or ordering argument exists in the branch list contract.

#### Presentation

- **FR-024**: The commit view MUST NOT display a total commit count for the branch and MUST rely on paging alone. The total number of commits since a repository's origin is seldom what a user needs, and computing it costs a separate pass over the whole history. No total is offered in the response contract either: an unused field would still carry that cost the first time anything selected it, and a nullable field can be added without breaking consumers if a caller ever needs one. _Verify_: assert no total is rendered, and that no pass over the whole history exists anywhere in the read path. The bounded `imported..head` count FR-006 requires is not a total and is unaffected.

#### Operating the read-only check

These extend the read-only check above (FR-015 to FR-020). They are what makes it a background job an operator can live with.

- **FR-025**: Overlapping checks of the same repository MUST NOT accumulate, whether they arrive from the schedule or on demand. While a check for that repository is in progress, a further request MUST NOT perform a second check, and MUST report the check in progress where it can identify it. "Check" here means the work against the remote, not the scheduling record: a duplicate request may be admitted and then find the repository already claimed, in which case it does no remote work and reports the claim it found. _Verify_: trigger the check repeatedly, faster than it completes, and assert exactly one check performs remote work while the later requests either report the in-flight one or complete without contacting the remote.
- **FR-026**: A check that fails for one repository MUST NOT prevent the remaining repositories from being checked, and MUST NOT leave the failed repository unchecked until a further interval has elapsed. The failure MUST be recorded with the repository and the reason. _Verify_: point a fixture repository at an unreachable remote, run a cycle, and assert the other repositories are still checked, the failure is recorded, and the next cycle retries the failed repository rather than treating it as already checked.
- **FR-027**: Each check cycle MUST record how many repositories it checked, how many had moved and how many failed. Each detected movement MUST be recorded with the repository, the ref, and the commits it moved from and to. _Verify_: run a cycle over one moved and one unchanged repository; assert the cycle record carries all three counts and that exactly one movement record is present with those fields.

#### Accessibility of commit state

- **FR-028**: Each commit state and each marker MUST be conveyed by a text label or an icon with an accessible name, not by colour alone, and the copy action MUST announce its completion to assistive technology. The two markers and the pending range are the whole answer this feature gives, so conveying them by colour alone would withhold that answer from part of the audience. _Verify_: assert every state and marker is identifiable from its accessible name alone, with colour information disregarded.

### Key Entities *(include if feature involves data)*

No new entities. The data model is unchanged.

- **Repository (read-write and read-only kinds)**: gains a read-only projection of its git state. No attributes added, none modified.
- **Tracked commit** (existing, branch-aware, optional on all repository kinds): supplies Infrahub's side of the comparison. Already present, already branch-scoped, already written by the import path. This feature never writes it.
- **Tracked ref** (existing, branch-aware, read-only repositories): determines which history the commit log describes. Two Infrahub branches may legitimately pin different refs. This feature never writes it.
- **Commit**: deliberately NOT an entity. A value read from Git, identified by its hash, never persisted. Each commit carries hash, message, author, date and an explicit state relative to the imported commit and the head. This is the central decision of the feature.
- **Freshness**: two distinct values, both reported alongside a git-derived answer. When the answering worker last updated its local copy, and, for read-only repositories, when the remote was last checked for movement. They differ whenever a check confirmed that nothing had moved, which is the common case for a quiet repository.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can determine whether a specific pushed commit has been imported without opening worker logs, running orchestrator commands, or contacting OpsMill.
- **SC-002**: Diagnosis of "my commit has not appeared" moves from roughly two hours with Solution Architecture involvement to self-service in the product. A user can read a repository's recent commits, and what Infrahub is running, from inside Infrahub, without visiting the git remote or comparing hashes by hand. This holds whether or not anything is wrong: the same view serves ordinary curiosity about a repository's history and the specific question of whether a commit was picked up.
- **SC-003**: Adding a repository costs time and storage independent of its commit count: a repository with 10,000 commits adds no more Infrahub data than one with 10.
- **SC-004**: The first page of commits appears in under 2 seconds for a repository with 10,000 commits of history.
- **SC-005**: Drift is reported for a repository with 200 branches in a single request to a worker, and both the worker request count and the database query count are the same as for a repository with 5 branches.
- **SC-006**: A commit pushed to a read-only repository's tracked ref becomes visible in Infrahub within the configured interval with no user action, and immediately on demand.
- **SC-007**: A rewritten tracked ref is reported as rewritten and never as ordinary drift.
- **SC-008**: The background check never changes which commit a read-only repository is running, measured across a full test cycle in which the remote advances, is rewritten, and has a tag moved.
- **SC-009**: Repeated reads of the same repository return the same facts regardless of which worker answers. Verified through the convergence broadcast (FR-017) rather than by running a multi-worker fixture in this slice; the freshness statement is what exposes a worker that has fallen behind.
- **SC-010**: When no worker holds a local copy, the view reaches a resolved state with no user action beyond waiting.
- **SC-011**: No merge conflict and no proposed-change diff entry is ever attributable to commit data.
- **SC-012**: When no worker can answer, the request fails within the configured bound with a retry hint instead of hanging, and the branch list still shows its rows.
- **SC-013**: An unreachable or hanging remote on one read-only repository does not delay that repository's imports, does not stop the other repositories being checked, and is visible to an operator without reading worker logs line by line.
- **SC-014**: An operator who finds the check too frequent can lengthen its interval through configuration alone, taking effect at the next cycle with no deployment or schedule rewrite. The setting is read from the environment like every other, so applying it follows the same path as any other configuration change.

## Assumptions

- Git data comes from a task worker's existing local copy, not from a Git provider's API, so arbitrary remotes keep working with no provider-specific integration and no additional credentials.
- The read path never fetches from the remote. Freshness is bounded by two distinct intervals: roughly one minute for read-write repositories via the existing periodic sync, and the configurable read-only interval introduced here, default 15 minutes. That default is settled as a starting point rather than a tuned value; an idle repository costs only a refs listing per interval, so it can be lowered without a redesign once real usage shows whether it is too slow.
- The existing read-write periodic sync already converges every worker on each successful cycle (it broadcasts a fetch-and-checkout to the whole pool unconditionally, verified in the current code on 2026-09-03). The convergence requirement (FR-017) therefore only needs stating for read-only repositories. This resolves the PRD's first open question.
- Local copies carry full history. No shallow or single-branch cloning exists today, so a log is available for both repository kinds, including a read-only repository pinned to a ref.
- Fleet convergence via broadcast remains the mechanism that makes workers consistent. This work triggers it for a new case rather than replacing it, and accepts that it is best-effort; the freshness statement covers the gap.
- Convergence carries the currently-imported commit rather than the new head, so the step that makes workers consistent cannot become the step that moves the pin forward.
- A worktree checked out at a commit protects that commit from garbage collection, which is what makes forcing tag updates safe. This is asserted by FR-020 rather than assumed. Validated during planning and recorded in research.md: the detached worktree at `commits/<sha>` is a reachability root, nothing in the backend runs `git gc` or `git worktree prune`, and the worker's global git config does not touch `gc.auto`, so only git's opportunistic auto-gc runs and it respects worktree roots. FR-020 still tests it, because the failure mode is losing the commit Infrahub is running.
- Paging is by page size and offset, matching the existing convention for lists in the product.
- The commit view is a new area of the repository page. The drift column extends the Branches card delivered by the sibling PRD rather than replacing it. If that card does not exist yet, User Story 3 has no rows to annotate.
- The Branches card obtains the drift column through a second request, settled during planning: the drift data is exposed as its own top-level query rather than fanned out from the card's resolver. Either option satisfied FR-022, and the requirement that survives is that the rows never depend on the drift column. Recorded for the sibling PRD to consume rather than re-decide.
- The drift list's row set matches the Branches card's: branches synchronised with Git for read-write repositories, every branch for read-only repositories, excluding merged and deleting branches and the global branch. A drift column whose rows differed from the card's would not line up with it.
- Infrahub's per-branch tracked values for one repository are read in a single database query rather than one per branch. That query reproduces the existing per-branch resolution exactly, including the inheritance that makes a never-imported branch report its origin branch's fork-point value; it does not change what any branch reports.
- The not-yet-available state and the rewritten-ref condition are presented as distinct states of the commit view without introducing a new repository status value. Their exact visual treatment follows the frontend design canvas.
- The design canvas needs three matching updates: the commit-count badge is dropped (FR-024), the freshness line carries a check time as well as an update time for read-only repositories (FR-007), and read-only repositories gain a "check remote now" action whose placement the canvas should settle (FR-015).
- Commit visibility follows the access rules that already govern repositories. No new permission and no new access surface.
- A rewritten ref is reported, not resolved. No automatic action is taken on it.

## Deviations from the source PRD

Every point at which this specification departs from the PRD, with the reason. Anything not listed
here should match the PRD.

- **PRD FR-015's non-interleaving MUST is narrowed.** The PRD says the check "MUST NOT interleave with other git operations on the same local copy". FR-019 confines that to the steps which modify the local copy and requires the remote listing to hold no lock at all. Reason: git applies no network timeout by default, so holding the repository lock across `ls-remote` lets an unreachable remote block that repository's imports for an unbounded period. The listing changes nothing locally, which is what makes moving it out safe.
- **PRD's "concurrency limit of one, cancelling new runs" is replaced.** FR-025 uses a per-repository claim key instead. Reason: the Prefect limit is per deployment, so one repository's on-demand run would cancel another's. The consequence is stated in FR-025 and in the quickstart: a duplicate request may be admitted, submit a run, and that run then finds the claim and exits without contacting the remote. One check does remote work; ten concurrent callers do not all receive one task id.
- **No total commit count at all.** PRD FR-008 requires "no total count unless requested", its edge case calls the total optional, and its reader module includes it. FR-024 removes it from the response contract entirely. Resolved with the PRD author on 2026-09-03: a count since the repository's origin is seldom what a user needs, and an unused field still costs a full pass over the history the first time anything selects it.
- **PRD FR-016's verification narrows from every worker to one.** FR-020 keeps the requirement and tests it on a single worker, because what protects the commit is its own worktree acting as a reachability root, which is identical on every worker rather than a property of the fleet.
- **The warm-up trigger is not a named protocol.** The PRD's design constraints require it declared as a protocol in the reader's own vocabulary with the publisher wired at the entry point. It is inline in the log reader instead. Reason: the property that constraint protected, single-flight behaviour testable without patching, is delivered by a recording cache and `WorkflowRecorder` in T044.
- **The unavailable path and warm-up triggering sit on the worker, not in the API-layer read client.** The PRD assigns both to its "Git read client". The answering worker is what knows whether it holds a clone, which the PRD's own FR-011 implies, so detection and the collapsed trigger live there and the client is left as RPC plus timeout.
- **A read-write branch not synchronised with Git is absent from the branch list** rather than present and un-drifted. The PRD's edge case says such a branch "must not be reported as drift"; excluding it from the row set satisfies that and matches the sibling card's rows, which a differing row set would not line up with.
- **The remote-branch mapping is extracted** into `infrahub.git.branch_mapping`, with the existing
  private method delegating to it. The PRD says the commit log reader should take its ref as an
  explicit parameter "without refactoring it". Deliberate override: the API server cannot call a
  private instance method and must never build a repository object, so it needs the rule as a
  function; and restating the rule in the resolver would leave two copies to drift on precisely the
  default-branch case that [INFP-670](https://opsmill.atlassian.net/browse/INFP-670) is fixing. The
  extracted copy takes all three inputs as required parameters, which is what keeps it free of the
  `or registry.default_branch` fallback that PRD is removing. Coordination recorded on that epic.
- **Two configuration settings, not one.** The PRD scopes configuration to "one new interval knob".
  The bounded wait needs a timeout setting as well. Both are in the governance table below, and the
  timeout is the one that changes behaviour for existing callers.
- **A new graph query, reading per-branch values the PRD assigned to the sibling.** The PRD's module
  list has none, treating this feature's drift path as purely git-derived and giving every
  graph-resolved per-branch value to the sibling PRD. `RepositoryBranchValuesQuery` reads the tracked
  commit and ref per branch here. Two reasons: FR-004 bounds the database query count as well as the
  worker request count, which the PRD did not, and a drift row cannot say a branch has drifted
  without the value it drifted from. What stays with the sibling is the card itself, its row
  rendering, its other graph-resolved values such as import status, and the cross-repository query
  with server-side filtering, ordering and paging. This query is the single-repository primitive that
  epic widens rather than a second implementation of it, and that boundary needs confirming with the
  IFC-3104 owner before its own pull request lands, not after. It has its own governance row below.
- **Classification runs on the worker, not in the API business layer.** The PRD assigns "Commit visibility comparison" to the API layer. It lives in `git/state/classification.py` and executes on the worker beside the git reads that feed it. The property the PRD was protecting, pure logic reachable and testable without a message bus, is preserved: the module has no I/O and its own unit tests.
- **Four requirements and three success criteria have no PRD counterpart.** FR-026, FR-027 and FR-028, and SC-012, SC-013 and SC-014, were added after the dual-lens critique: they cover operating the read-only check as a background job an operator can live with, accessibility of the commit states, and the degradation behaviour the PRD left implicit. Additions rather than departures, listed here so this register accounts for every difference in both directions.
- **Three test-tier changes.** Two of the PRD's agreed unit tests, the commit log reader and the
  bounded RPC wait, land as component tests: both do real I/O, against a clone and against a bus
  adapter respectively. The pure classification they wrap keeps its unit tests, which is where the
  logic the PRD wanted covered actually lives. The PRD's integration-level handler tests also land at
  component level, still against a real `FileRepo` clone, so the substance is preserved at a cheaper
  tier. The PRD's integration-level GraphQL check is not moved: an interim draft downgraded it and it
  is restored at integration level, because a recording double cannot show that the real transport is
  also lazy.
- **The multi-worker test is not built.** Reasoning and revisit trigger in
  `checklists/requirements.md`.

## Out of Scope

- [INFP-557](https://opsmill.atlassian.net/browse/INFP-557) in full: per-commit import outcomes, rejected commits with validator errors, and the activity view. Two forward-compatibility measures are in scope: per-commit state comes from the system rather than being inferred from list position, and the hash is the row identity, so a later hash-keyed outcome store joins on without reshaping the contract.
- Expanding a commit to inspect its changes.
- Commit search and filtering. If added later, it must be part of the request contract; filtering a fetched page client-side is not an acceptable substitute.
- Pinning a repository to a chosen commit ([INFP-672](https://opsmill.atlassian.net/browse/INFP-672)), which this work unblocks both by providing the list to choose from and by keeping read-only remotes current enough for that list to be meaningful.
- Any change to read-only import semantics. The background check is visibility-only by design.
- Automatic action on a rewritten ref.
- Import-error status, global operational status, and gating merges on branch state (the other [INFP-671](https://opsmill.atlassian.net/browse/INFP-671) candidates, and [INFP-670](https://opsmill.atlassian.net/browse/INFP-670)).
- Extra columns on the global branches view.
- The Branches card itself: its row rendering, and the graph-resolved values on it beyond the tracked commit and ref, such as import status. Those belong to the sibling PRD, and User Story 3 adds a column to that card rather than building it. The exception, recorded under Deviations, is that this feature does read the tracked commit and ref per branch, because a drift row cannot report drift without the value it drifted from.
- The cross-repository branch-status query with server-side filtering, ordering, counting and paging. The single-repository per-branch read built here is the primitive that query extends.
- Filtering, ordering or counting branches by drift. Not achievable while the remote head is read live rather than stored.
- Storing a per-branch remote head. Revisit when one request per page proves insufficient in practice, or when drift needs to become a server-side filter, order or count.
- A commit count badge. A count relative to the default branch (commits on this branch not on the default branch) might be useful later, but the commit view is not split along that line in this slice.

## Dependencies

- **Sibling PRD / IFC-3104** (Cross-branch repository status query): delivers the Branches card rows that User Story 3 annotates. User Stories 1 and 2 do not depend on it. The single-repository per-branch read built here is the primitive that PRD's core primitive and its periodic-sync refactor extend. It is built here so this feature's own drift read is not one query per branch; that PRD widens it to many repositories with server-side filters, ordering and paging rather than writing a second one.
- **Existing worker-side local copies and the worker fetch broadcast**: the mechanism this feature reads from and converges through.
- **Existing error catalogue and retry-hint convention**: the bounded-wait failure (FR-012) is delivered as one new catalogued error.
- **Configuration reference documentation**: gains two new settings, the worker RPC timeout and the read-only check interval, and must be regenerated.

## Governance Gates

Using the "Ask First" list from the project's agent instructions.

| Gate | Status |
| --- | --- |
| Database schema or migration changes | Ruled out. No new node kind, no new attribute, no migration, no new write to any existing repository attribute. |
| GraphQL schema modifications | Requires sign-off. Additive read field or fields, an on-demand trigger for the read-only check, plus one error catalogue code and typed payload. |
| New dependencies | None. |
| CI/CD workflow changes | None. |
| Authentication / authorization changes | Ruled out. No new permission and no new access surface. The two queries reuse the existing repository view permission; the on-demand refs-check mutation gates on update permission for the concrete kind, exactly as `ReadOnlyRepositoryImportLastCommit` already does. |

Additional items with comparable reach:

| Item | Why it matters |
| --- | --- |
| Shared-path change | Bounding the wait on the worker request path affects every existing caller of that path, including the current git file read. Should land as its own reviewed change. |
| New scheduled background check and configuration default | Adds standing background load proportional to the number of read-only repositories, and a new configuration setting, which means regenerating the configuration reference documentation. |
| New graph query for per-branch repository values | Reads existing data and changes no schema, but it is new graph-query surface that the sibling epic extends and the periodic sync later depends on. Reviewed on its own merits, with the per-branch resolution pinned by test. |
