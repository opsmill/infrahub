# Feature Specification: Filter a repository's branches by sync status

**Feature Branch**: `ple-repo-branches-sync-filter-ifc-3471`

**Created**: 2026-10-20

**Status**: Draft

**Input**: Jira [IFC-3471](https://opsmill.atlassian.net/browse/IFC-3471), the follow-up identified in [IFC-3156](https://opsmill.atlassian.net/browse/IFC-3156): "The Branches section on the repository's page has no Sync Status filter. It should have one, so a user can list only the failing branches without the GraphQL sandbox."

## Clarifications

### Session 2026-10-20

- Q: Should the active filter tag show the Sync Status label or the stored value? → A: The label ("Import Error"), without changing the tag display of other object tables; a dedicated tag display for the Branches section is acceptable.
- Q: Should the Status filter tag also show a label? → A: No. Only the Sync Status tag shows a label; the Status tag keeps its current display (`OPEN`).
- Q: How does the shared tag display show the label without changing other tables? → A: An opt-in `showChoiceLabels` flag on the shared filter tags, set only by the Branches section (user, during planning).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - List only the branches that failed to import (Priority: P1)

An operator opens a repository's page (Integrations, Git Repositories, then the repository). The Branches section lists every Infrahub branch with its Status, Sync Status and Commit. The operator wants to know which branches failed to import the latest commit, so they filter the list by Sync Status "Import Error" and view only those branches, without writing a GraphQL query.

**Why this priority**: This is the need stated in IFC-3156. Today the only way to list the failing branches is the GraphQL sandbox.

**Independent Test**: On a repository with several branches, one of them with Sync Status "Import Error", apply the Sync Status filter "Import Error" from the filter picker and check that only that branch is listed and the count next to the heading reads 1.

**Acceptance Scenarios**:

1. **Given** the Branches section of a repository, **When** the operator opens the filter picker, **Then** a "Sync Status" field is offered next to the branch name and Status fields.
2. **Given** the operator selected the "Sync Status" field, **When** they open its value list, **Then** the five sync status values are offered with the labels the Sync Status column uses: Unknown, Import Error, Tracked Ref Missing, In Sync, Syncing.
3. **Given** the operator applied Sync Status "Import Error", **When** the list refreshes, **Then** only branches whose Sync Status column shows "Import Error" are listed, and the number next to the "Branches" heading is the number of matching branches, not the total.
4. **Given** a Sync Status filter is applied, **When** the operator removes its active filter tag, **Then** the unfiltered list returns.
5. **Given** no branch has the selected Sync Status, **When** the filter is applied, **Then** the section shows the empty state for filters that match nothing ("No branch matches these filters"), not the empty state for a repository with no branches.

---

### User Story 2 - Filter from the Sync Status column header (Priority: P2)

The operator reads the Sync Status column and wants to narrow the list from there, the same way they can from the Status column header.

**Why this priority**: Decided by the user on 2026-10-20. The column header is disabled today only because no filter existed.

**Independent Test**: Open the Sync Status column header menu, apply a value, and check that the result, the active filter tag and the URL are the same as when the filter is applied from the filter picker.

**Acceptance Scenarios**:

1. **Given** the Branches section, **When** the operator opens the Sync Status column header, **Then** the header offers a filter action and no sort action.
2. **Given** the operator applies a value from the column header, **When** the list refreshes, **Then** the rows, the active filter tag and the stored filter are the same as for the same value applied from the filter picker.

---

### User Story 3 - Combine, page and share a filtered list (Priority: P3)

The operator narrows the list with several criteria and shares the result with a colleague.

**Why this priority**: The Sync Status filter must behave like the existing name search and Status filter, which already combine, reset paging and persist in the URL.

**Independent Test**: Apply a name search, a Status filter and a Sync Status filter together, reload the page, and check that all three are restored and that the list shows only branches that match all three.

**Acceptance Scenarios**:

1. **Given** a name search "feat" and Status "Open", **When** the operator adds Sync Status "Import Error", **Then** only open branches whose name contains "feat" and whose Sync Status is "Import Error" are listed.
2. **Given** the operator is on page 3 of the list, **When** they apply, change or remove the Sync Status filter, **Then** the list returns to page 1.
3. **Given** a Sync Status filter is applied, **When** the operator reloads the page or opens the shared URL, **Then** the filter, its active filter tag and the filtered list are restored.
4. **Given** a URL whose stored Sync Status value is not one of the Sync Status values, **When** the page loads, **Then** the list is not narrowed by sync status.

---

### Edge Cases

- A branch that has not imported anything of its own shows the Sync Status inherited from the default branch. The filter matches the value the column shows, inherited or not.
- A read-only repository's Branches section ("Infrahub branches") offers the same filter, because both repository kinds have a sync status.
- The Sync Status value of a branch changes between two refreshes, for example from "Syncing" to "In Sync". The list reflects the value at the time of each refresh; a branch can leave the filtered list.
- The filter offers only the "contains" condition, like the other two fields, because the list cannot be narrowed to branches with no sync status.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Branches section MUST offer a Sync Status filter in its filter picker, next to the branch name and Status filters.
- **FR-002**: The Sync Status filter MUST offer exactly the five sync status values (Unknown, Import Error, Tracked Ref Missing, In Sync, Syncing), shown with the same labels as the Sync Status column.
- **FR-003**: Applying a Sync Status value MUST list only the branches whose Sync Status equals that value, as the Sync Status column shows it, including values inherited from the default branch.
- **FR-004**: The number next to the "Branches" heading and the paging controls MUST reflect the filtered set.
- **FR-005**: The Sync Status filter MUST combine with the branch name search and the Status filter: a branch is listed only when it matches all active filters.
- **FR-006**: The Sync Status column header MUST offer the same filter, and MUST NOT offer sorting.
- **FR-007**: Applying, changing or removing the Sync Status filter MUST return the list to its first page.
- **FR-008**: The Sync Status filter MUST be stored with the section's other filters in the page URL, so a reload or a shared URL restores it.
- **FR-009**: A stored Sync Status value that is not one of the Sync Status values MUST be ignored, so the list is not narrowed by it.
- **FR-010**: The filter MUST be available on the Branches section of both read-write and read-only repositories.
- **FR-011**: The active filter tag for the Sync Status filter MUST show the value's label ("Import Error"), not the stored value ("error-import"). The Status filter tag in the Branches section and filter tags in other object tables MUST keep their current display; if the shared tag display cannot show the label without changing them, the Branches section uses a dedicated tag display of its own (decided by the user on 2026-10-20).

### Key Entities

- **Branch sync status**: the state of a repository on one Infrahub branch: Unknown, In Sync, Import Error, Tracked Ref Missing or Syncing. A branch that has not imported anything of its own inherits the default branch's value.
- **Branches section filter**: one condition the operator applies to the list, made of a field (branch name, Status or Sync Status) and a value. All filters in the section apply together and are stored in the page URL.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator lists only the branches with Sync Status "Import Error" on a repository's page in at most 4 clicks, with no GraphQL query.
- **SC-002**: For every one of the five values, the filtered list contains exactly the branches whose Sync Status column shows that value, and the number next to the heading equals the number of those branches.
- **SC-003**: A URL copied from a filtered list restores the same filtered list for another user with access to the repository.
- **SC-004**: Existing behaviour of the name search and the Status filter is unchanged, and filter tags in other object tables display exactly as before.

## Assumptions

- The list is narrowed on the server, which already accepts one sync status value per request, counts the filtered rows and pages them after filtering. No backend change is needed.
- The filter takes one value at a time. A filter for "any failure" (Import Error or Tracked Ref Missing) is out of scope, because the list can be narrowed to one value per request.
- The values are offered in the order the repository's sync status attribute declares them.
- Sorting by sync status is out of scope.
- One end-to-end test covers User Story 1, as the project constitution requires for user-facing features (Principle IV). Component tests cover the other scenarios.
- The API documentation already describes the sync status argument of the branch status query. Whether the user documentation needs a note about the new filter is decided in the documentation phase.
