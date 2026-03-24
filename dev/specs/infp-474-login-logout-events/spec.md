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
3. **Given** authentication events exist, **When** an administrator queries all authentication events for a specific account, **Then** all login and logout events within the platform's standard retention window are returned in chronological order.
4. **Given** login and logout events exist, **When** the event feed is filtered by event type, **Then** only authentication events of the specified type are returned.

---

### Edge Cases

- What happens when a user's session is administratively invalidated (forced logout)? A logout event is emitted attributed to the account being logged out, distinguishing it from a user-initiated logout.
- What happens when a user logs in and immediately logs out within the same second? Both events are recorded with accurate timestamps and the same session identifier.
- How does the system handle a logout request for an already-expired or non-existent session? No logout event is emitted if no valid session exists to invalidate.
- What happens if event emission fails after a successful login? The authentication itself succeeds; event emission failure does not prevent login. The event may be absent from the audit trail.
- What happens if the same account logs in from multiple concurrent sessions? Each session generates its own independent login event with a unique session identifier.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST emit a login event for every successful interactive authentication via password, OAuth2, or OIDC.
- **FR-002**: Successful login events MUST include: account identifier, authentication method (password/OAuth2/OIDC), session identifier, and timestamp.
- **FR-003**: System MUST emit a logout event when a user explicitly initiates a logout.
- **FR-004**: Logout events MUST include: account identifier, session identifier, logout type (`user_initiated` or `admin_forced`), and timestamp.
- **FR-005**: Authentication events (`infrahub.account.*`) MUST be queryable via the existing activity event interface, filterable by account identifier, event type, and time range — and accessible only to users with admin role.
- **FR-006**: API key authentication (per-request, non-interactive) MUST NOT generate login or logout events.
- **FR-007**: Automatic session expiry (session times out without explicit user action) MUST NOT generate a logout event.
- **FR-008**: System MUST emit a logout event with `logout_type="admin_forced"` when an administrator invalidates a user's session via the API or GraphQL interface.

### Key Entities *(include if feature involves data)*

- **Login Event**: Records a successful authentication — account identifier, authentication method, session identifier, timestamp, and optional group/role context.
- **Logout Event**: Records a session termination — account identifier, session identifier, timestamp, and logout type (`user_initiated` or `admin_forced`).
- **Session Reference**: A unique identifier that links a login event to its corresponding logout event, enabling session duration analysis.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Login and logout events appear in the activity event feed within 5 seconds of the authentication action under normal load.
- **SC-002**: Administrators can retrieve all authentication events for a specific user within the platform's standard event retention window without missing entries.
- **SC-003**: Authentication events (`infrahub.account.*`) are accessible only to users with admin role via the activity event interface — non-admin users cannot query these events.
- **SC-004**: Zero successful authentication events are silently dropped under normal operating conditions.

## Clarifications

### Session 2026-03-24

- Q: Should the system emit a logout event when an administrator invalidates a user's session? → A: Yes — emit `AccountLoggedOutEvent` with `logout_type="admin_forced"` when an admin invalidates a session.
- Q: Should `client_ip` and `user_agent` be stored as-is or anonymized? → A: Store as-is; no anonymization required for this internal tool.
- Q: What is the retention policy for authentication events? → A: Same as all other activity events in the platform — no special retention configuration required.
- Q: Who can query `infrahub.account.*` events? → A: Admin users only. Non-admin users must not be able to query authentication events.

## Dependencies & Assumptions

- The existing activity event system and its query interface are in place and functioning.
- "Interactive authentication" is defined as password login, OAuth2 callback, and OIDC callback — not API key per-request verification.
- "Explicit logout" is defined as either a user-initiated logout action or an administrator-forced session invalidation — not automatic session expiry.
- Event storage retention follows the same policy as all other activity events in the system. No special retention configuration is required.
- `client_ip` and `user_agent` are stored as-is in event payloads. No anonymization is required; Infrahub is an internal infrastructure tool where audit completeness takes precedence.
- Access to `infrahub.account.*` events is restricted to admin users. The admin role check is enforced at the query layer, consistent with how other privileged data is protected in Infrahub.
