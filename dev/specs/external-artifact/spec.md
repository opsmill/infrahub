# Feature Specification: Artifacts rendered by an external engine

**Feature Branch**: `external-artifact`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "I want the ability to have and render artifacts external to Infrahub using an external execution engine. For example people might want to render using Ansible, or also render using Python externally, or use a rendering engine that they might use externally. However I want the artifact to end up in Infrahub as an artifact."

No Jira or JPD ticket exists for this feature yet. The branch step ran without one on the user's instruction.

## User Scenarios & Testing *(mandatory)*

The primary user is an automation team whose configuration templates already run in an external rendering engine: AWX or Ansible, a custom API, or another tool. Today, to get artifacts in Infrahub, with diffs in proposed changes and regeneration when data changes, the team has to rewrite those templates as Infrahub Jinja2 or Python transformations. With this feature, the team keeps its templates in its engine. Infrahub decides when each artifact must be rendered again, sends the engine the data to render from, and stores the result as a normal artifact.

### User Story 1 - Review an externally rendered configuration change in a proposed change (Priority: P1)

An engineer changes device data on a branch and opens a proposed change. Infrahub selects the artifacts the change affects, using the same analysis of the GraphQL query that it uses for internal artifacts, and asks the external engine to render them. The engine renders each artifact and sends the content back. The engineer views the configuration diff in the proposed change before merging.

**Why this priority**: The value of keeping artifacts in Infrahub is that reviewers view the effect of a data change before merge. Without this journey, an external artifact would be a file upload that is not linked to the branch data.

**Independent Test**: Can be fully tested with one artifact definition that uses an external transformation, one target device and a reference engine. Change the device on a branch, open a proposed change, and check that the artifact diff shows the content returned by the engine.

**Acceptance Scenarios**:

1. **Given** artifact definition `startup-config` uses an external transformation and has `Ready` artifacts for every device in group `edge-routers`, **When** an engineer changes the description of an interface on `edge-01` on branch `change-123` and opens a proposed change, **Then** Infrahub emits one render request, for `edge-01` only, and the artifact for `edge-01` on that branch shows `Pending`.
2. **Given** a render request for `edge-01` is pending, **When** the engine sends back the rendered content with the token from that request, **Then** the artifact becomes `Ready`, the artifact check on the proposed change passes, and the proposed change shows the configuration diff for `edge-01`.
3. **Given** the render request was delivered through a webhook that has a Python transformation attached, **When** Infrahub delivers the request, **Then** the engine receives the output of that transformation, for example an AWX job launch body, and the output contains the render token and the callback address.
4. **Given** the branch from scenario 2 is merged, **When** Infrahub runs its regeneration after the merge, **Then** it emits a render request for `edge-01` on the destination branch, and the artifact on the destination branch becomes `Ready` when the engine answers.

---

### User Story 2 - Release a new template version and review its effect (Priority: P2)

The template team changes its templates in the external engine. Their CI commits a new version value for the external transformation to the repository connected to Infrahub, on a branch. Infrahub treats the version change like a change to transformation code: it renders every artifact of that definition again on the branch, and the proposed change shows the diff for every target.

**Why this priority**: Infrahub cannot detect changes to templates stored outside it. Without this journey, a template change would leave every artifact showing `Ready` with outdated content.

**Independent Test**: Can be fully tested by committing a new version value on a branch for a definition with three targets, and checking that three render requests are emitted and the proposed change shows three artifact diffs.

**Acceptance Scenarios**:

1. **Given** an external transformation declares version `1.4.0` in `.infrahub.yml`, **When** the CI commits version `1.5.0` on branch `template-1-5` and the repository is synchronized, **Then** Infrahub emits a render request for every target of the definition on `template-1-5`.
2. **Given** an artifact definition that uses an external transformation, **When** a user triggers regeneration of the definition manually, **Then** Infrahub emits a render request for every target of the definition on that branch.

---

### User Story 3 - Find out that the external engine failed (Priority: P3)

The engine reports an error, or does not answer before the timeout. The engineer views a failed artifact check on the proposed change, with the engine's message, and the merge is blocked if checks are required.

**Why this priority**: The engine is outside Infrahub's control. Without this journey, an artifact could stay `Pending` indefinitely, and the proposed change would never complete.

**Independent Test**: Can be fully tested with a reference engine that reports an error for one target and does not answer for another.

**Acceptance Scenarios**:

1. **Given** a render request is pending, **When** the engine reports a failure with the message "template variable `mtu` undefined", **Then** the artifact becomes `Error` and the artifact check fails with that message.
2. **Given** a render request is pending, **When** the timeout of the external transformation passes without an answer, **Then** the artifact becomes `Error` and the artifact check fails with the message "no response from engine".
3. **Given** a render request timed out, **When** the engine sends content for it afterwards, **Then** Infrahub rejects the content and the artifact stays unchanged.

---

### Edge Cases

- **Data changes again while a render is pending**: Infrahub emits a new render request. The token of the earlier request is no longer accepted, so an older result cannot overwrite a newer one.
- **The engine answers after the timeout**: Infrahub rejects the answer and the artifact stays `Error`.
- **The engine sends content with a token issued for another artifact or another branch**: Infrahub rejects it and no artifact changes.
- **The template changes outside Infrahub and nobody updates the version value**: Infrahub does not detect the change. The team triggers regeneration manually (User Story 2, scenario 2).
- **A device leaves the target group**: Infrahub removes its artifact, the same as for internal artifacts, and emits no render request for it.
- **The engine cannot be reached from Infrahub**: the webhook delivery fails and the render request times out, so the artifact becomes `Error`. Engines that Infrahub cannot reach over the network are not supported in this version.
- **The query result for a target is very large**: the render request still carries the full query result (see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Infrahub MUST select artifacts that use an external transformation for regeneration with the same analysis of the GraphQL query it uses for internal artifacts, after data changes on a branch, in proposed changes and after a merge.
- **FR-002**: For each selected target, Infrahub MUST run the definition's GraphQL query on the branch and include the full result in the render request. The engine renders from that data only.
- **FR-003**: Infrahub MUST emit a dedicated render-request event type for each artifact to render, and users MUST be able to subscribe a webhook to that event type.
- **FR-004**: Each render request MUST include the render ID, the render token, the callback address, the target, the branch, the artifact definition and the query result.
- **FR-005**: Users MUST be able to attach a Python transformation to the webhook that delivers render requests, so that the request matches the format of their engine. All the content listed in FR-004 MUST be available to that transformation.
- **FR-006**: Users MUST be able to declare an external transformation, its GraphQL query, its version value and the artifact definitions that use it in `.infrahub.yml`, in a repository connected to Infrahub.
- **FR-007**: A change to the version value of an external transformation on a branch MUST select every target of the definitions that use it on that branch for regeneration.
- **FR-008**: Users MUST be able to trigger regeneration of an artifact definition that uses an external transformation manually, in the same way as for internal artifact definitions.
- **FR-009**: Each render token MUST only allow submitting the result of its render request, for that artifact on that branch, and MUST expire when the request times out or a newer request replaces it.
- **FR-010**: Infrahub MUST store submitted content as the artifact's content, set the artifact to `Ready`, and record the result on the artifact check of an open proposed change, the same as for an internal render.
- **FR-011**: The engine MUST be able to report a failure with a message. Infrahub MUST then set the artifact to `Error` and fail the artifact check with that message.
- **FR-012**: Infrahub MUST keep the artifact `Pending` while it waits for the engine. When the timeout of the external transformation passes without an answer, Infrahub MUST set the artifact to `Error` and fail the artifact check.
- **FR-013**: Infrahub MUST reject submissions with an expired, replaced or mismatched token, and MUST leave the artifact unchanged when it rejects one.
- **FR-014**: Infrahub MUST reject submitted content larger than the maximum content size, or of a content type the artifact definition does not declare.
- **FR-015**: Users MUST be able to set the timeout on each external transformation.

### Key Entities

- **External transformation** (new): describes rendering by an engine outside Infrahub. Like the existing Jinja2 and Python transformations, it belongs to a repository and has a GraphQL query. It adds a version value and has a longer default timeout. Artifact definitions reference it in the same way they reference internal transformations.
- **Render-request event** (new): emitted once per artifact to render. It carries the content listed in FR-004. Webhooks subscribe to it.
- **Render token** (new): a credential limited to one render request. It is valid from the moment the request is emitted until the request ends, times out or is replaced.
- **Artifact** (existing): no change to what it represents. It uses the existing `Pending`, `Ready` and `Error` statuses.
- **Artifact definition** (existing): no change to what it represents. It can now reference an external transformation.
- **Custom webhook with a Python transformation** (existing): delivers the render request and reshapes it for the engine.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the same data change, Infrahub selects external artifacts for regeneration on exactly the same targets as an internal artifact definition with the same query and target group.
- **SC-002**: A reference engine written as a plain HTTP script, using no Infrahub libraries, completes User Story 1.
- **SC-003**: An artifact becomes `Ready` less than 5 seconds after the engine submits valid content.
- **SC-004**: 100% of render requests end in `Ready` or `Error` within the timeout of their external transformation plus 1 minute.
- **SC-005**: Infrahub rejects 100% of submissions with an expired, replaced or mismatched token, and none of them changes an artifact.
- **SC-006**: A team with existing templates in an external engine connects them to an artifact definition without changing any template file. They only add the declaration in `.infrahub.yml`, the webhook and the step that sends the result back.

## Assumptions

- The external engine can receive HTTP requests from Infrahub's task workers, and can send an HTTP request back to Infrahub.
- The engine sends results in a format Infrahub defines. For AWX, the last task of the playbook sends the result. Infrahub does not transform incoming results.
- Template teams can commit a version change to the repository connected to Infrahub, for example from their template CI.
- The default timeout for external transformations is 10 minutes, because external jobs such as AWX job templates take longer than the 60-second default of internal transformations. The user did not decide this value, so planning should confirm it.
- The maximum content size for externally rendered artifacts is the existing maximum file size setting of the object store (50 MB by default). Internal artifacts have no size limit today, so planning chose this existing setting (research R5).
- The query result for one target fits within the size limits of the event and the webhook delivery. Planning must check these limits.
- After a merge, the engine receives a second render request for the destination branch. Teams accept this extra load.
- Submitting a result is a new authentication path for an external system, and needs a security review.

### Out of scope for this version

- Engines that fetch render requests from Infrahub, for engines that Infrahub cannot reach over the network.
- Transforming the results that engines send back.
- External engines for generators, checks and computed attributes.
- Content types beyond those artifacts support today.
- Infrahub starting, scaling or managing the engine.
- UI forms for creating external transformations. They are declared only in `.infrahub.yml`.
- Rendering several targets in one render request.
