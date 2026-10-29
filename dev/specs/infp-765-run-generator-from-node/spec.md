# Feature Specification: Run a Generator for a Node from the Node's Page

**Feature Branch**: `run-generator-from-node-infp-765`

**Created**: 2026-10-28

**Status**: Draft

**Jira**: [INFP-765](https://opsmill.atlassian.net/browse/INFP-765)

**Input**: User description: *"Run a generator for a node from the node's page."* The idea was stress-tested in a grilling session on 2026-10-28; the JPD card holds the agreed requirements.

## Background

A network engineer who builds a design in Infrahub runs generators for individual nodes as part of an automation workflow. In the solution-ai-dc demo, building a new data center means creating a fabric on a branch, adding it to the `fabrics` group, and running the `generate-fabric` generator for it; trigger rules then start the pod and rack generators.

Today the engineer starts that run from the generator definition, not from the fabric:

1. Open Actions > Generator Definitions.
2. Open the generator definition, for example `generate-fabric`.
3. Select Run > Selected targets.
4. Pick the node from the list of the target group's members.

The engineer must know which generator definition applies to the node, because the node's page does not show which generators target it. A node that is missing from the target group is not offered in the target list, and nothing tells the engineer why.

This feature adds a Generators section to the Actions menu of a node's page. It lists the generator definitions that target the node and starts a run for that node only.

## Design Principles

**Behave as the generator definition page does.** A run started from a node's page is the same run as one started from the generator definition page with that node selected. Anything this spec does not state explicitly — confirmation, repeated clicks, which group members count — follows the generator definition page.

**Hide what cannot apply; disable what cannot run yet.** A node whose kind no generator targets shows nothing. A node of a targeted kind that is missing from the target group shows the generator disabled, with the reason, so the engineer knows what to fix.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start a generator for a node from its page (Priority: P1)

On a branch, the engineer opens the page of a node that is a member of a generator definition's target group, opens the Actions menu, and selects "Run <generator definition>" in the Generators section. One run of that generator starts for this node only. A message confirms the start and links to the task; the engineer follows progress with the existing background-task indicator.

**Why this priority**: This is the core of the feature: starting the generator from the node the engineer is working on, as one step of an automation workflow.

**Independent Test**: On a branch, open the page of a member of a target group, select the generator in the Actions menu, and verify that one run starts for that node only and that the message links to the task.

**Acceptance Scenarios**:

1. **Given** a branch where Fabric-E is a member of the `fabrics` group, the target group of `generate-fabric`, and the engineer is signed in, **When** they select "Run generate-fabric" in the Actions menu of Fabric-E's page, **Then** one `generate-fabric` run starts for Fabric-E only, and a message confirms the start with a link to the task.
2. **Given** the run from scenario 1 has finished, **When** the engineer views the result, **Then** it is the same as a run started from the generator definition page for Fabric-E: the same generator instance is created or updated, and trigger rules start the same downstream generators.
3. **Given** a node targeted by two generator definitions whose target groups both contain it, **When** the engineer opens the Actions menu, **Then** the Generators section lists one "Run" item per generator definition.

---

### User Story 2 - View generators only where they apply (Priority: P2)

The Generators section appears only on the pages of nodes that a generator targets, and only for users who are allowed to run generators on the current branch.

**Why this priority**: Without these rules, the Actions menu of every node would carry generator items that cannot apply or that the user is not allowed to use.

**Independent Test**: Open the page of a node whose kind no target group contains, and open the same node's page as a user without permission on the default branch; verify that neither shows a Generators section.

**Acceptance Scenarios**:

1. **Given** a node whose kind is not contained in any generator definition's target group, for example a location, **When** the engineer opens its Actions menu, **Then** no Generators section appears.
2. **Given** a member of a target group on the default branch, **When** a signed-in user without the `edit_default_branch` permission opens its Actions menu, **Then** no Generators section appears.
3. **Given** the same node on the default branch, **When** a user with the `edit_default_branch` permission opens its Actions menu, **Then** the Generators section appears.
4. **Given** a member of a target group on a branch other than the default branch, **When** any signed-in user opens its Actions menu, **Then** the Generators section appears.
5. **Given** a deployment that allows anonymous read access, **When** a user who is not signed in opens the page of a member of a target group, **Then** no Generators section appears.

---

### User Story 3 - Understand why a generator cannot run for a node (Priority: P3)

When a node's kind is targeted by a generator definition but the node itself is not a member of the target group, the item is shown disabled, and its tooltip names the target group. After the engineer adds the node to the group, the item becomes available.

**Why this priority**: A new node that someone forgot to add to the target group is a common step in the data center workflow; naming the group tells the engineer what to fix.

**Independent Test**: Create a node of a targeted kind outside the target group, verify the disabled item and its tooltip, add the node to the group, and verify that the item becomes available.

**Acceptance Scenarios**:

1. **Given** a branch where the `fabrics` group contains other fabrics but not Fabric-F, **When** the engineer opens the Actions menu of Fabric-F's page, **Then** "Run generate-fabric" is shown disabled, and its tooltip says Fabric-F is not a member of the target group `fabrics`.
2. **Given** scenario 1, **When** the engineer adds Fabric-F to the `fabrics` group and opens the Actions menu again, **Then** "Run generate-fabric" is available.
3. **Given** Fabric-F is a member only of a child group of `fabrics`, **When** the engineer opens its Actions menu, **Then** "Run generate-fabric" is shown disabled, because generators run only for direct members of the target group.

---

### Edge Cases

- **Empty target group**: when a generator definition's target group has no members, no node counts as a target of that definition, so its item does not appear anywhere until the first member is added.
- **Mixed kinds in a target group**: a node of any kind that the target group contains counts as a target of that definition.
- **Repeated selection**: the item is disabled only while the start request is being sent. A second selection afterwards starts a second run, as on the generator definition page; runs already in progress are not checked.
- **Node leaves the target group after the page loaded**: the run starts, runs no generator, and is still reported as started. This matches the generator definition page and is out of scope to change.
- **Start request refused**: when the server refuses the run, for example because the user lacks a permission the page did not anticipate, an error message shows the server's reason.
- **IP prefix and IP address pages**: these pages share the node Actions menu, so the Generators section follows the same rules there.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST list, in the Actions menu of a node's page, one "Run <generator definition>" item for each generator definition whose target group contains at least one node of the same kind as the node.
- **FR-002**: System MUST NOT show a Generators section on the page of a node whose kind no generator definition's target group contains.
- **FR-003**: System MUST disable the item for a generator definition when the node is not a direct member of that definition's target group, and MUST name the target group in the item's tooltip.
- **FR-004**: System MUST NOT show a Generators section to users who are not signed in.
- **FR-005**: System MUST NOT show a Generators section on the default branch to users without the `edit_default_branch` permission.
- **FR-006**: Users MUST be able to start a run of one generator definition for the node only, from the node's Actions menu.
- **FR-007**: System MUST confirm that the run started with a message that links to the run's task, and MUST show the server's reason when the run is refused.
- **FR-008**: A run started from a node's page MUST produce the same result as a run started from the generator definition page for the same node: the same generator instance and the same downstream runs started by trigger rules.
- **FR-009**: System MUST NOT ask for confirmation before starting the run, and MUST disable the item only while the start request is being sent.
- **FR-010**: The Generators section MUST follow the same rules on every page that uses the node Actions menu, including IP prefix and IP address pages.

### Key Entities *(include if feature involves data)*

- **Generator definition** (existing): a generator from a Git repository, with one target group. A run executes the generator once per selected member.
- **Target group** (existing): the group whose direct members a generator definition runs for. Any group can be a target group.
- **Target node** (existing concept, rule defined here): a node counts as a target of a generator definition when the definition's target group contains at least one node of the same kind.
- **Generator instance** (existing): records the run of one generator definition for one node.
- **Task** (existing): the background run that the confirmation message links to.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a target node's page, an engineer starts a generator for that node in two selections (open the Actions menu, select the generator), compared with five steps through the generator definition page today.
- **SC-002**: On every node page, the listed generators are exactly the generator definitions whose target group contains the node's kind: none missing, none extra.
- **SC-003**: A user who is not allowed to run generators on the current branch never views the Generators section.
- **SC-004**: A run started from a node's page and a run started from the generator definition page for the same node produce the same generator instance and the same downstream runs.

## Assumptions

- The feature changes only what the user interface offers. How Infrahub runs a generator, and who the server allows to run one, do not change.
- The visibility rules mirror what the server already enforces when a run starts: a signed-in user is required everywhere, and the `edit_default_branch` permission is required on the default branch. On other branches every signed-in user may run every generator; Infrahub has no permission dedicated to running generators.
- Hiding the section is a convenience, not an access control: the server remains the authority, and a refused run reports the server's reason.
- Generator definitions and target group membership are read on the branch the user is viewing.
- The generator writes its data through the task worker's account, not the user's account. This is existing behavior and is not changed.

## Out of Scope

- A permission dedicated to running generators.
- Rejecting, at the server, a run for a node that is not a member of the target group.
- Showing the run's result, or the downstream runs, on the node's page. The background-task indicator covers progress.
- Applying the default-branch visibility rule to the existing Run buttons on the generator definition and generator instance pages.
- Running a generator for several nodes selected in a list view.
