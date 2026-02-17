# Feature Specification: Custom HTTP Headers for Webhooks

**Feature Branch**: `infp-445-webhook-headers`
**Created**: 2026-02-17
**Status**: Draft
**Input**: INFP-445 - Add custom headers for webhooks and custom webhooks
**Related**: INFP-470 - Customer feature request for custom HTTP headers on webhooks

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Attach Authentication Headers to a Webhook (Priority: P1)

An infrastructure administrator configures a webhook in Infrahub to notify an external system (e.g., Ansible Automation Platform) about infrastructure changes. The external system requires an authentication header such as `Authorization: Bearer <token>` to accept incoming requests. The administrator creates a key-value pair containing the sensitive header credentials, associates it with the webhook, and when events fire, the custom header is automatically included in the HTTP request.

**Why this priority**: This is the core use case driving the feature. Without it, customers cannot integrate Infrahub webhooks with any system requiring header-based authentication, which is the majority of modern APIs and automation platforms.

**Independent Test**: Can be fully tested by creating a key-value pair with a sensitive header value, linking it to a webhook, triggering an event, and verifying the target system receives the request with the correct authentication header.

**Acceptance Scenarios**:

1. **Given** a webhook configured to notify an external system and a key-value pair containing a sensitive authentication header, **When** the administrator links the key-value pair to the webhook and an event fires, **Then** the HTTP request to the external system includes the custom authentication header with the correct value.
2. **Given** a key-value pair with a sensitive header value (e.g., API key or bearer token), **When** the administrator views the key-value pair via the UI, **Then** the sensitive value is masked and not displayed in cleartext.
3. **Given** a webhook with a linked authentication header, **When** the administrator queries the webhook configuration, **Then** the header relationship is visible.

---

### User Story 2 - Use Environment Variable-Based Headers for Secret Management (Priority: P2)

An operations team manages secrets through an external secret manager (e.g., Kubernetes secrets, HashiCorp Vault via environment variable injection, Delinea safe). Rather than storing the actual secret value in Infrahub, they create a key-value pair that references an environment variable name. At webhook send time, the actual secret value is resolved from the environment of the worker process.

**Why this priority**: This enables enterprise-grade secret management workflows where sensitive credentials never touch Infrahub's database, which is critical for security-conscious organizations and compliance requirements.

**Independent Test**: Can be fully tested by creating an environment-variable-based key-value pair, setting the corresponding environment variable in the worker environment, triggering a webhook, and verifying the resolved value is sent in the request header.

**Acceptance Scenarios**:

1. **Given** a key-value pair configured with an environment variable reference and the variable is set in the worker environment, **When** a webhook event fires, **Then** the system resolves the environment variable at send time and includes the actual value in the HTTP header.
2. **Given** a key-value pair configured with an environment variable reference and the variable is NOT set in the worker environment, **When** a webhook event fires, **Then** the system skips that header, sends the request with all remaining resolvable headers, and logs a warning identifying the missing variable name.
3. **Given** a key-value pair referencing an environment variable, **When** an administrator views the configuration, **Then** only the environment variable name is displayed (not the resolved value).

---

### User Story 3 - Reuse Headers Across Multiple Webhooks (Priority: P3)

An administrator has multiple webhooks that all target systems within the same organization and require the same authentication header. Instead of duplicating the header configuration for each webhook, they create a single key-value pair and associate it with multiple webhooks. When they need to rotate a credential, they update the key-value pair in one place and all linked webhooks automatically use the new value.

**Why this priority**: Reduces configuration overhead and simplifies credential rotation, which directly impacts operational efficiency and security hygiene.

**Independent Test**: Can be fully tested by creating one key-value pair, linking it to two or more webhooks, triggering events on each webhook, and verifying all requests include the correct header.

**Acceptance Scenarios**:

1. **Given** a key-value pair linked to multiple webhooks, **When** events fire on different webhooks, **Then** each webhook request includes the same custom header with the correct value.
2. **Given** a key-value pair linked to multiple webhooks, **When** the administrator updates the header value, **Then** subsequent webhook requests from all linked webhooks use the updated value.
3. **Given** a key-value pair linked to multiple webhooks, **When** the administrator removes the key-value pair from one webhook, **Then** the remaining webhooks continue to use the header while the unlinked webhook no longer sends it.

---

### User Story 4 - Add Non-Sensitive Custom Headers to a Webhook (Priority: P3)

An administrator needs to include non-sensitive identification or routing headers (e.g., `X-Source-System: infrahub`, `X-Tenant-Id: acme-corp`) in webhook requests. They create a plain-text key-value pair where the value is stored and displayed without masking, and associate it with their webhook.

**Why this priority**: Supports simpler use cases where headers carry non-sensitive metadata, providing flexibility without requiring secret management overhead.

**Independent Test**: Can be fully tested by creating a plain-text key-value pair, linking it to a webhook, triggering an event, and verifying the header appears in the request.

**Acceptance Scenarios**:

1. **Given** a plain-text key-value pair linked to a webhook, **When** a webhook event fires, **Then** the HTTP request includes the custom header with the literal value.
2. **Given** a plain-text key-value pair, **When** the administrator views it via the API or UI, **Then** the value is displayed in cleartext (not masked).

---

### Edge Cases

- What happens when a custom header uses the same name as a system-reserved header (e.g., `Content-Type`, `webhook-signature`)? The user's custom header value takes precedence, overriding the system default.
- What happens when multiple key-value pairs linked to the same webhook define the same header name? The system warns the administrator but allows it, using the last-associated value when sending the request.
- What happens when a key-value pair is deleted but still referenced by webhooks? The relationship should be cleanly removed and the webhook should continue to function without that header.
- What happens when the webhook cache contains stale header data after a header value is updated? Cache must be invalidated when header nodes or their webhook relationships change.
- What happens when an environment variable header references a variable name that contains special characters? The system should validate environment variable names follow standard conventions.
- How does the system behave when a webhook has a very large number of custom headers? A reasonable upper bound should be enforced to prevent abuse.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow users to create key-value pairs representing custom HTTP headers with a human-friendly name (globally unique across all key-value pair types, consistent with standard generic behavior in Infrahub), a header name (the actual HTTP header field name), and a header value.
- **FR-002**: System MUST support three types of key-value pairs: plain-text (value stored and displayed as-is), password/sensitive (value uses a Password attribute kind and is masked in the UI), and environment-variable-based (value resolved from worker environment at send time).
- **FR-003**: System MUST allow associating zero or more key-value pairs with any webhook (both Standard and Custom Webhooks).
- **FR-004**: System MUST support many-to-many relationships between key-value pairs and webhooks, allowing one key-value pair to be referenced by multiple webhooks and one webhook to reference multiple key-value pairs.
- **FR-005**: System MUST include all associated custom headers in webhook HTTP requests when events fire.
- **FR-006**: System MUST merge custom headers with default system headers (Content-Type, Accept, HMAC signature headers) when sending webhook requests. In case of name conflicts, the user's custom header value MUST take precedence over the system default.
- **FR-007**: System MUST mask sensitive header values (password type) in the UI, consistent with how existing Password kind attributes are displayed.
- **FR-008**: System MUST resolve environment-variable-based header values from the worker process environment at the time the webhook request is sent, not at configuration time.
- **FR-009**: When an environment-variable-based header references a variable that does not exist in the worker environment, the system MUST skip that header, include all remaining resolvable headers in the request, and log a warning identifying the missing variable name.
- **FR-010**: System MUST invalidate cached webhook data when associated key-value pairs are created, updated, deleted, or when the relationship between a key-value pair and a webhook changes.
- **FR-011**: System MUST allow management of key-value pairs and their webhook associations through both the GraphQL API and the Web UI.
- **FR-012**: System MUST clearly document that authentication header values (e.g., Bearer tokens) require the user to include the full value including any type prefix (e.g., "Bearer " before the token).
- **FR-013**: Key-value pair entities (the generic and all node types) MUST be branch-agnostic, consistent with existing webhook behavior.

### Key Entities

- **Key-Value Pair (Generic)**: A reusable generic configuration object representing a key-value pair. Has a globally unique human-friendly name for identification (enforced across all key-value pair types, per standard Infrahub generic behavior), a key name (e.g., an HTTP header field name like "Authorization" or "X-Auth-Token"), and a value. Serves as the base generic entity with three specialized node types that inherit from it, differing only in how the value is stored and resolved.
- **Static Key-Value Pair (Node)**: A node type inheriting from the Key-Value Pair generic. The value is stored as plain text and displayed without masking. Used for non-sensitive data like system identifiers or routing metadata.
- **Password Key-Value Pair (Node)**: A node type inheriting from the Key-Value Pair generic. The value uses a Password attribute kind and is masked in the UI. Used for sensitive data like API keys and bearer tokens.
- **Environment Variable Key-Value Pair (Node)**: A node type inheriting from the Key-Value Pair generic. The stored value is the name of an environment variable. The actual value is resolved from the worker process environment at the time of use. Used when secrets are managed externally (Kubernetes secrets, vault solutions).
- **Webhook**: An existing generic entity (CoreWebhook) from which both Standard and Custom Webhook types inherit. A new optional `headers` relationship (cardinality=many) to the Key-Value Pair generic MUST be defined on this webhook generic, so that all webhook types automatically inherit the ability to reference zero or more key-value pairs.

## Assumptions

- The key-value pair naming follows `CoreKeyValue` as a generic base type rather than HTTP-header-specific naming, enabling potential reuse for non-webhook use cases in the future (per review feedback from Patrick Ogenstad).
- Key-value pairs are branch-agnostic to match existing webhook behavior.
- The existing 2-hour webhook cache mechanism will be extended to include header data, with appropriate cache invalidation.
- Environment variables are resolved on the Prefect worker where webhooks execute; Kubernetes operators or infrastructure admins are responsible for ensuring the required environment variables are available in the worker pods.
- There is no limit on the number of headers per webhook for the initial implementation, though a reasonable guard-rail may be added based on performance testing.

## Clarifications

### Session 2026-02-17

- Q: How should the system handle multiple key-value pairs linked to the same webhook that define the same header name? → A: Warn but allow; the last-associated value is used when sending the request.
- Q: When an environment variable header references a missing variable, should the entire webhook delivery fail or just that header? → A: Skip the unresolvable header, send remaining headers, log a warning.
- Q: Should the key-value pair name be globally unique across all types? → A: Yes, globally unique across all key-value pair types, consistent with standard Infrahub generic behavior.
- Q: Does the feature need special audit logging for key-value pair lifecycle events? → A: No; rely on existing Infrahub audit/change tracking for node mutations. No feature-specific observability required.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can successfully send webhook requests to external systems requiring custom authentication headers (e.g., Ansible Automation Platform) without any workarounds or intermediary proxies.
- **SC-002**: Users can configure a webhook with custom headers and trigger a successful authenticated request to an external endpoint. This should be verified after the configuration has been updated and applied within Prefect.
- **SC-003**: Sensitive header values (password type) are masked in the UI and never appear in application logs.
- **SC-004**: A single key-value pair update propagates to all linked webhooks on the next event trigger, with zero manual intervention required per webhook.
- **SC-005**: Environment-variable-based headers resolve correctly at send time, and missing variables produce actionable error messages that identify the specific variable name.
- **SC-006**: Custom header functionality works identically for both Standard and Custom Webhook types with no behavioral differences.
