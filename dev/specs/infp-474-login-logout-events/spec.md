# Feature Specification: Login/Logout Activity Events

**Feature Branch**: `infp-474-login-logout-events`
**Created**: 2026-03-23
**Status**: Draft
**Input**: User description: "Add Login/Logout Activity Events"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Authentication Audit Trail (Priority: P1)

A security auditor or administrator needs to review who logged in and out of Infrahub, when, and via which authentication method. They query the activity event feed filtered by a specific user or time window to produce an audit report for compliance or incident investigation purposes.

**Why this priority**: The core value of this feature is a queryable authentication audit trail. Without this story there is no feature. Compliance and security investigations are high-stakes use cases that require completeness and accuracy.

**Independent Test**: Can be fully tested by performing a login and logout, then querying the event feed filtered by account and event type — confirms both events appear with correct details and delivers standalone audit value.

**Acceptance Scenarios**:

1. **Given** a user authenticates successfully via password, **When** the activity event feed is queried for that user, **Then** a login event appears with the account identifier, authentication method, session identifier, and timestamp.
2. **Given** a user explicitly logs out, **When** the activity event feed is queried for that user, **Then** a logout event appears with the account identifier, session identifier, and timestamp.
3. **Given** a 30-day time window, **When** an administrator queries all authentication events for a specific account, **Then** all login and logout events within that window are returned in chronological order.
4. **Given** login and logout events exist, **When** the event feed is filtered by event type, **Then** only authentication events of the specified type are returned.

---

### User Story 2 - Failed Login Detection (Priority: P2)

A security administrator wants to detect suspicious authentication patterns, such as repeated failed login attempts or brute-force attacks. They query the event feed for failed login events to identify the source and investigate.

**Why this priority**: Failed login tracking is the primary security signal for detecting attacks. It requires handling partial information (no account ID for unknown users) and is a key differentiator from simply logging successful sessions. It builds on P1 infrastructure and extends it with security monitoring capability.

**Independent Test**: Can be fully tested by submitting an incorrect password login attempt and querying for failed login events — confirms the attempted identifier and failure reason are captured without requiring a valid account.

**Acceptance Scenarios**:

1. **Given** a login attempt with an incorrect password for an existing account, **When** the activity event feed is queried, **Then** a failed login event appears with the account identifier, failure reason, and timestamp.
2. **Given** a login attempt with a username that does not exist, **When** the activity event feed is queried, **Then** a failed login event appears with the attempted username as identifier, failure reason, and timestamp — no account identifier is included.
3. **Given** multiple failed login attempts in a short window, **When** the event feed is queried for failed login events, **Then** each attempt appears as a separate event with its own timestamp.

---

### User Story 3 - Automation Triggers on Authentication Events (Priority: P3)

An operator has configured webhook integrations to react to Infrahub activity events. They want login or logout events to trigger those webhooks — for example, notifying a channel when an administrator logs in, or sending an alert when repeated failed logins are detected.

**Why this priority**: Webhook/automation integration multiplies the value of authentication events, enabling security monitoring pipelines without custom development. It depends on P1 events being correctly emitted and queryable, so it is lower priority.

**Independent Test**: Can be fully tested by configuring an existing webhook trigger for the login event type, authenticating, and confirming the webhook fires — no new webhook infrastructure is needed.

**Acceptance Scenarios**:

1. **Given** a webhook is configured to trigger on login events, **When** a user successfully authenticates, **Then** the webhook fires with the login event payload.
2. **Given** a webhook is configured to trigger on failed login events, **When** a failed authentication attempt occurs, **Then** the webhook fires with the failed event payload.
3. **Given** a webhook is configured to trigger on logout events, **When** a user explicitly logs out, **Then** the webhook fires with the logout event payload.

---

### Edge Cases

- What happens when a user's session is administratively invalidated (forced logout)? A logout event is emitted attributed to the account being logged out, distinguishing it from a user-initiated logout.
- What happens when OAuth2 or OIDC authentication fails during the callback phase? A failed login event is emitted with the authentication method and available error context.
- What happens when a user logs in and immediately logs out within the same second? Both events are recorded with accurate timestamps and the same session identifier.
- How does the system handle a logout request for an already-expired or non-existent session? No logout event is emitted if no valid session exists to invalidate.
- What happens if event emission fails after a successful login? The authentication itself succeeds; event emission failure does not prevent login. The event may be absent from the audit trail.
- What happens if the same account logs in from multiple concurrent sessions? Each session generates its own independent login event with a unique session identifier.
- How are attempted usernames from failed logins for non-existent accounts handled safely? The attempted identifier is stored as-is and treated as untrusted input in all downstream contexts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST emit a login event for every successful interactive authentication via password, OAuth2, or OIDC.
- **FR-002**: Successful login events MUST include: account identifier, authentication method (password/OAuth2/OIDC), session identifier, and timestamp.
- **FR-003**: System MUST emit a login event for every failed interactive authentication attempt via password, OAuth2, or OIDC.
- **FR-004**: Failed login events MUST include: attempted username or identifier, authentication method, failure reason, and timestamp. When the user account does not exist, no account identifier is included.
- **FR-005**: System MUST emit a logout event when a user explicitly initiates a logout.
- **FR-006**: Logout events MUST include: account identifier, session identifier, and timestamp.
- **FR-007**: Authentication events MUST be queryable via the existing activity event interface, filterable by account identifier, event type, and time range.
- **FR-008**: API key authentication (per-request, non-interactive) MUST NOT generate login or logout events.
- **FR-009**: Automatic session expiry (session times out without explicit user action) MUST NOT generate a logout event.
- **FR-010**: Authentication events MUST be usable as triggers for existing webhook and automation integrations without additional configuration to the integration layer.

### Key Entities *(include if feature involves data)*

- **Login Event**: Records a single authentication attempt — outcome (success/failure), account identifier (if known), authentication method, session identifier (if authenticated), failure reason (if failed), timestamp.
- **Logout Event**: Records an explicit session termination — account identifier, session identifier, timestamp.
- **Session Reference**: A unique identifier that links a login event to its corresponding logout event, enabling session duration analysis.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Login and logout events appear in the activity event feed within 5 seconds of the authentication action under normal load.
- **SC-002**: Administrators can retrieve all authentication events for a specific user across any 30-day window without missing entries.
- **SC-003**: Authentication events are queryable alongside all other activity events using the existing query interface with no additional configuration required.
- **SC-004**: Existing webhook integrations can be configured to trigger on login, failed login, or logout events without new development work on the integration layer.
- **SC-005**: Every failed login attempt is captured with sufficient detail (attempted identifier and failure reason) to support a security investigation.
- **SC-006**: Zero successful authentication events are silently dropped under normal operating conditions.

## Dependencies & Assumptions

- The existing activity event system and its query interface are in place and functioning.
- The existing webhook integration mechanism supports filtering by event type without modification.
- "Interactive authentication" is defined as password login, OAuth2 callback, and OIDC callback — not API key per-request verification.
- "Explicit logout" is defined as a user-initiated logout action — not automatic session expiry.
- Event storage retention follows the same policy as all other activity events in the system.
- Failed logins for non-existent usernames capture the attempted string as an identifier; this string is treated as untrusted user input in all downstream contexts.
