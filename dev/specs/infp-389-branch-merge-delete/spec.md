# Feature Specification: Delete Branch After Merge

**Feature Branch**: `infp-389-branch-merge-delete`
**Created**: 2026-02-19
**Status**: Draft
**Input**: User description: "INFP-389 - Add the ability to delete branches after they have been merged using a proposed change, or regular branch merge"
**Jira**: [INFP-389](https://opsmill.atlassian.net/browse/INFP-389)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Global Configuration for Branch Deletion (Priority: P1)

As an Infrahub administrator, I want to configure branch deletion behavior globally via the Infrahub configuration file so that I can set organizational defaults for automatic branch cleanup after merge.

**Why this priority**: Configuration must exist before any automatic behavior can function. This is foundational to all other stories and has zero risk since settings default to disabled.

**Independent Test**: Can be fully tested by setting the branch deletion options in the Infrahub configuration file, restarting the service, and verifying the settings are reflected when performing merges.

**Acceptance Scenarios**:

1. **Given** an administrator edits the Infrahub configuration file, **When** they add the branch deletion settings, **Then** the system recognizes options for "delete branch after merge" and "delete branch from Git repository after merge".
2. **Given** an administrator changes a branch deletion setting in the configuration file, **When** the service is restarted, **Then** the setting takes effect for all subsequent merges.
3. **Given** the settings have never been configured, **When** the system starts with defaults, **Then** both settings are disabled (opt-in behavior).

---

### User Story 2 - Automatic Branch Deletion After Merge (Priority: P1)

As an infrastructure engineer, I want branches to be automatically deleted after a successful merge so that I don't accumulate stale branches in Infrahub that cause clutter, confusion, and maintenance overhead.

**Why this priority**: This is the core value proposition. Merged branches that linger cause increasing memory consumption as their schemas diverge from the default branch. Automatic cleanup after merge prevents this resource growth and reduces maintenance overhead.

**Independent Test**: Can be fully tested by enabling the global configuration, merging a branch, and verifying the branch no longer appears in the branch list. Delivers immediate value by eliminating manual cleanup.

**Acceptance Scenarios**:

1. **Given** the global setting for branch deletion after merge is enabled, **When** a user merges a branch via a standard branch merge, **Then** the branch is automatically deleted from Infrahub after the merge completes successfully.
2. **Given** the global setting for branch deletion after merge is enabled, **When** a user merges a branch via a proposed change, **Then** the branch is automatically deleted from Infrahub after the proposed change merge completes successfully.
3. **Given** the global setting for branch deletion after merge is disabled, **When** a user merges a branch, **Then** the branch remains in Infrahub and is not automatically deleted.
4. **Given** the global setting is enabled and a merge fails, **When** the merge operation encounters an error, **Then** the branch is not deleted and the user is informed of the merge failure.

---

### User Story 3 - Automatic Git Branch Deletion After Merge (Priority: P2)

As an infrastructure engineer using Git-synced repositories, I want the corresponding Git branch to also be automatically deleted when the Infrahub branch is deleted after merge, so that both Infrahub and the Git repository stay in sync and free of stale branches.

**Why this priority**: Many users have Git-synced repositories and expect branch lifecycle consistency between Infrahub and Git. Without this, users still have to manually clean up Git branches even if Infrahub branches are auto-deleted.

**Independent Test**: Can be fully tested by setting both the branch deletion and Git branch deletion options in the configuration file, merging a branch that is synced with a Git repository, and verifying the branch is deleted from both Infrahub and the Git repository.

**Acceptance Scenarios**:

1. **Given** both "delete branch after merge" and "delete Git branch after merge" global settings are enabled and the branch is synced with a Git repository, **When** a user merges the branch, **Then** the branch is deleted from both Infrahub and the Git repository.
2. **Given** "delete branch after merge" is enabled but "delete Git branch after merge" is disabled, **When** a user merges a Git-synced branch, **Then** only the Infrahub branch is deleted; the Git branch remains.
3. **Given** the Git branch deletion fails (e.g., permission error, network issue), **When** the system attempts to delete the Git branch, **Then** the failure is recorded in the task log of the repository (including the repository name), and the Infrahub branch deletion still proceeds.
4. **Given** a branch is synced with multiple Git repositories and deletion fails on one of them, **When** the system attempts to delete the Git branch across repositories, **Then** the failure is recorded in the task log of each affected repository, and successful deletions on other repositories are not rolled back.

---

### User Story 4 - Manual Branch Deletion with Git Option (Priority: P3)

As an infrastructure engineer, when the automatic branch deletion setting is disabled, I want a way to manually delete a merged branch with the option to also delete it from Git, so that I can clean up branches on my own schedule while still having access to Git cleanup.

**Why this priority**: Provides a fallback for users who prefer manual control over branch lifecycle. The option to also delete from Git in one action saves extra steps.

**Independent Test**: Can be fully tested by merging a branch with auto-delete disabled, navigating to the branch detail view, clicking the delete button (with and without the Git delete option), and verifying the branch is removed accordingly.

**Acceptance Scenarios**:

1. **Given** a branch has been merged and auto-delete is disabled, **When** the user views the branch detail, **Then** a delete button is visible.
2. **Given** the user clicks the delete button on a merged Git-synced branch, **When** the deletion dialog appears, **Then** the user is presented with an option to also delete the branch from the Git repository (only shown when the global Git deletion setting is not already enabled).
3. **Given** the user confirms deletion with the Git option selected, **When** the branch is deleted, **Then** both the Infrahub branch and the Git branch are removed; if the Git deletion fails, the failure is recorded in the task log of the repository.

---

### Edge Cases

- What happens when a branch is associated with multiple proposed changes, some merged and some not? The branch should only be auto-deleted after the final merge that resolves all associated proposed changes.
- How does the system handle deletion of a branch that has already been manually deleted? The system should handle this gracefully (no error if the branch no longer exists).
- What happens if the Infrahub branch deletion succeeds but Git branch deletion fails? The Infrahub deletion should not be rolled back; the failure is recorded in the task log of the repository.
- What happens if a user attempts to delete a branch that is currently being merged? The deletion should be blocked or queued until the merge completes.
- How does the system handle Git branches that have been renamed or moved in the remote repository? The system should attempt deletion using the known branch name and report a clear error if the branch cannot be found.
- What happens when the Git repository is unreachable during deletion? The system should record the failure in the task log of the repository, allowing the user to investigate and retry or manually delete the Git branch.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a global configuration setting to enable or disable automatic branch deletion after merge.
- **FR-002**: System MUST provide a global configuration setting to enable or disable automatic Git branch deletion after merge (separate from the Infrahub branch deletion setting).
- **FR-003**: System MUST automatically delete the Infrahub branch after a successful standard branch merge when the global setting is enabled.
- **FR-004**: System MUST automatically delete the Infrahub branch after a successful proposed change merge when the global setting is enabled.
- **FR-005**: System MUST automatically delete the corresponding Git branch(es) after merge when the Git deletion global setting is enabled and the branch is synced with Git repositories.
- **FR-006**: System MUST NOT delete a branch if the merge operation fails.
- **FR-007**: System MUST record Git branch deletion failures in the task log of the affected repository, including the repository name.
- **FR-008**: System MUST provide a manual delete option for merged branches with the ability to also delete the Git branch.
- **FR-009**: System MUST present the Git deletion option only when the branch is Git-synced and the global Git deletion setting is not already enabled.
- **FR-010**: System MUST handle deletion failures for individual Git repositories independently when a branch is synced with multiple repositories, reporting per-repository results.
- **FR-011**: System MUST default both branch deletion settings to disabled (opt-in behavior) to preserve backward compatibility.
- **FR-012**: System MUST emit the existing branch deletion event when a branch is deleted post-merge, consistent with manual deletion behavior.
- **FR-013**: System MUST execute Git branch deletion asynchronously as a separate background job, not blocking the merge completion or the Infrahub branch deletion.
- **FR-014**: System MUST never delete the default/main branch, regardless of global configuration settings (hard-coded safeguard).

### Key Entities

- **Branch**: An Infrahub branch that tracks changes to infrastructure data. Can be associated with proposed changes and synced with one or more Git repositories.
- **Proposed Change**: A review workflow entity that wraps a branch merge. Upon merge completion, triggers branch deletion if configured.
- **Git Repository**: An external Git repository that may have a corresponding branch synced with an Infrahub branch.
- **Global Configuration**: System-wide settings defined in the Infrahub configuration file (`infrahub.toml`) that control branch lifecycle behavior, including deletion after merge.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users who enable auto-delete have zero stale merged branches accumulating in their branch list.
- **SC-002**: Branch deletion is scheduled immediately after a successful merge completes.
- **SC-003**: When Git branch deletion fails, 100% of failures are recorded in the task log of the affected repository, including the repository name.
- **SC-004**: Manual branch deletion from the UI completes in a single user action (one click plus confirmation).
- **SC-005**: Both global configuration settings default to disabled, ensuring no behavior change for existing users upon upgrade.
- **SC-006**: When a branch spans multiple Git repositories, deletion results are recorded per-repository in each repository's task log.

## Assumptions

- The existing branch deletion mechanism in Infrahub will be reused and extended (not replaced) to support post-merge deletion.
- Git branch deletion uses existing Git integration infrastructure (push-based deletion via the remote).
- The "delete Git branch" setting is only meaningful when "delete branch after merge" is also enabled or when manually deleting a branch.
- Branch deletion after merge for proposed changes follows the same lifecycle: the proposed change merge completes first, then the branch is deleted.
- The dependency on INFP-407 (referenced in the Jira ticket) is assumed to be resolved before this feature is implemented.
- Error handling for Git operations follows existing patterns in the codebase (retry logic, timeout handling, etc.).

## Dependencies

- **INFP-407**: This feature depends on the completion of INFP-407 as noted in the Jira ticket.

## Out of Scope

- User-level configuration overrides (global settings only for this iteration).
- Deletion of branches from the proposed change detail view based on the branch name string (deferred due to risk of accidentally deleting the wrong branch, as noted in the Jira ticket).
- Bulk branch cleanup or scheduled branch garbage collection.
- Branch archiving as an alternative to deletion.

## Open Questions

- **OQ-001**: Does deleting a branch in a Git repository require additional permissions beyond what Infrahub already has for Git operations (e.g., force-push or delete-ref permissions on the remote)?
- **OQ-002**: Should there be a unified permission model that combines the ability to delete branches in Infrahub with the ability to delete branches in Git, or should these remain separate capabilities?

## Clarifications

### Session 2026-02-19

- Q: What audit trail is needed for branch deletions (logging, notifications)? → A: The existing branch deletion event is already emitted; no new audit mechanism is needed. The same event should fire for post-merge auto-deletion as it does for manual deletion today.
- Q: Should Git branch deletion block the merge response, run in the merge pipeline, or be fully async? → A: Fully async. Git branch deletion runs as a separate background job after the merge completes; users are notified of results via event/log.
- Q: Should the default/main branch be protected from auto-deletion? → A: Yes, the default branch is always protected (FR-014). Note: the default branch is always the merge target, never the source branch being merged, so this is a defense-in-depth safeguard.
