# Feature Specification: Syslog Support for Infrahub

**Feature Branch**: `infp-384-syslog-support`
**Created**: 2026-02-25
**Status**: Draft
**Jira Reference**: [INFP-384](https://opsmill.atlassian.net/browse/INFP-384)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure and Stream Audit Events to Syslog (Priority: P1)

An Infrahub administrator at an enterprise organization needs to send audit events to a centralized SIEM system for security compliance. They add syslog configuration to the Infrahub configuration file, specifying the destination host, port, transport protocol, and log format. After restarting Infrahub, all tracked events automatically stream to the syslog destination in real-time without any further intervention.

**Why this priority**: This is the foundational capability that unblocks enterprise production deployments. Security teams at enterprise customers require all tools to send logs to a central location before granting production approval. Without basic syslog delivery, no other capability provides value.

**Independent Test**: Can be fully tested by configuring a single syslog destination, restarting Infrahub, performing a tracked action (e.g., creating an object), and verifying the event appears in a syslog receiver. Delivers the core compliance value immediately.

**Acceptance Scenarios**:

1. **Given** an Infrahub administrator with access to the configuration, **When** they add a syslog destination (host, port, UDP) and restart Infrahub, **Then** Infrahub connects to the syslog server and events begin flowing.
2. **Given** a configured syslog destination, **When** a user logs into Infrahub, **Then** a syslog event is emitted to the configured destination, containing the user identity, timestamp, and event type.
3. **Given** a configured syslog destination, **When** a user creates, updates, or deletes any object in Infrahub, **Then** a corresponding syslog event is emitted with the resource type, resource identifier, action, and outcome.
4. **Given** a configured syslog destination with RFC 5424 format, **When** an event is received by the syslog server, **Then** the event conforms to the RFC 5424 standard with the Infrahub event data as JSON in the message field.
5. **Given** an administrator who has not configured syslog, **When** Infrahub starts, **Then** no syslog connections are attempted and the system operates normally.

---

### User Story 2 - Secure Syslog Transport with TLS (Priority: P2)

An enterprise security administrator requires that audit logs transmitted to their SIEM are encrypted in transit. They configure Infrahub's syslog integration to use TLS over TCP, ensuring sensitive audit data cannot be intercepted during transmission across their network.

**Why this priority**: TLS is a security requirement for many enterprises, but the feature delivers significant compliance value even without it via plain TCP or UDP on secured internal networks. It is P2 because the core value is achieved first.

**Independent Test**: Can be tested by configuring a TLS-enabled syslog destination, verifying connections use TLS encryption, and confirming a non-TLS receiver rejects the connection while a TLS-enabled receiver accepts events normally.

**Acceptance Scenarios**:

1. **Given** a syslog destination configured with TLS enabled, **When** Infrahub starts, **Then** all syslog connections to that destination use TLS encryption.
2. **Given** a TLS-configured destination where the TLS handshake fails, **When** Infrahub attempts to connect, **Then** Infrahub logs a clear error and continues operating; the syslog destination is treated as unavailable.
3. **Given** a syslog destination configured without TLS, **When** Infrahub transmits events, **Then** events are sent in plain text over the configured protocol (TCP or UDP).

---

### User Story 3 - Multiple Syslog Destinations (Priority: P3)

An organization with multiple SIEM systems or log aggregators needs Infrahub to send audit events to more than one destination simultaneously. They configure multiple syslog destinations, each with its own independent settings, and all destinations receive the same events.

**Why this priority**: Multiple destinations add operational flexibility but the core compliance value is achieved with a single destination. This is P3 because it is listed as a "nice to have" in the product requirements.

**Independent Test**: Can be tested by configuring two separate syslog receivers, performing an action in Infrahub, and independently verifying the event appears in both receivers.

**Acceptance Scenarios**:

1. **Given** two syslog destinations configured, **When** a user performs a tracked action, **Then** the event is delivered to both destinations.
2. **Given** two syslog destinations where one becomes unavailable, **When** a tracked action occurs, **Then** events continue to be delivered to the available destination without interruption.
3. **Given** two destinations with different format settings (one RFC 5424, one RFC 3164), **When** an event occurs, **Then** each destination receives the event formatted according to its own configuration.

---

### User Story 4 - Forward Application Logs to Syslog (Priority: P4)

An operations team needs more than just audit events in their SIEM — they also want Infrahub's own operational log messages (warnings, errors, critical alerts from Infrahub components) forwarded alongside the audit stream. They enable application log forwarding for a destination in the configuration and set a minimum severity level so that only meaningful log entries are forwarded, without flooding the syslog server with low-level debug output.

**Why this priority**: Application log forwarding is operationally valuable but is not a compliance requirement on its own — the audit event stream (P1) satisfies compliance. This is P4 because it adds breadth of visibility for operations teams without being on the critical path for any customer deployment.

**Independent Test**: Can be tested by enabling application log forwarding on a destination with minimum severity WARNING, triggering a condition that produces a WARNING log in Infrahub, and verifying the log message appears at the syslog receiver. The audit event stream is fully independent and unaffected.

**Acceptance Scenarios**:

1. **Given** a syslog destination with application log forwarding enabled and minimum severity WARNING, **When** an Infrahub component emits a WARNING or ERROR log, **Then** that log message is forwarded to the syslog destination with the appropriate RFC 5424 severity field set.
2. **Given** the same configuration, **When** an Infrahub component emits a DEBUG or INFO log, **Then** that log message is NOT forwarded (filtered before enqueuing).
3. **Given** a syslog destination with application log forwarding enabled, **When** an audit event and an application log are forwarded to the same destination, **Then** they are distinguishable at the syslog receiver by their RFC 5424 FACILITY field.
4. **Given** a syslog destination with application log forwarding disabled (the default), **When** Infrahub emits any log message, **Then** no application log messages are forwarded; only audit events are sent.
5. **Given** high-frequency application log emission, **When** both audit events and application logs share the same destination queue, **Then** queue overflow drops application log records before audit events.

---

### Edge Cases

- What happens when a TCP syslog destination is unreachable at startup (including DNS resolution failure)? Infrahub starts normally, logs a warning to its own application logs, and the consumer task begins attempting connection using exponential backoff. The application is fully operational while reconnection attempts continue in the background.
- What happens when a UDP syslog destination is configured with an unreachable host? Infrahub starts normally and operates without any connectivity check. Datagrams sent to the host are silently lost or generate network errors that are not surfaced to the application. No connection state is maintained for UDP.
- What happens when the syslog server becomes unavailable mid-operation? Events already in the per-destination queue continue delivery attempts; events arriving while the queue is full are dropped and a warning is written to Infrahub's application logs.
- What happens when the syslog configuration contains a syntactically invalid value (e.g., port number out of range, missing required field, unsupported protocol value)? Infrahub fails to start with a clear, actionable error message. Hostname values are not validated at startup; DNS resolution is deferred to first connection attempt.
- What happens during high event volume where the queue fills faster than the syslog server can consume? Drop behavior differs by message type: an incoming application log record is discarded immediately without entering the queue; an incoming audit event evicts the oldest item currently in the queue to make room for itself. A warning is written to Infrahub's application logs in both cases.
- What happens when Infrahub is shut down gracefully? Each per-destination consumer drains its queue up to a configurable timeout before closing the connection. Events not delivered within the timeout are lost.
- What happens when an individual Infrahub worker process crashes? The in-memory queue for that worker is discarded; events pending in that queue at the time of the crash are not recovered.
- What happens when a UDP event payload exceeds the maximum UDP datagram size? The event is truncated at the MSG field boundary and a warning is logged. The truncated event is still delivered.
- What happens when a TCP connection is silently dropped by a firewall or NAT gateway? TCP keep-alive detects the dead connection and triggers reconnection. Events queued during this window are held until reconnection succeeds or the queue fills.
- What happens when application log forwarding is enabled and a log message is emitted by the syslog infrastructure itself (e.g., a log about a failed delivery)? These internal syslog service log messages are excluded from forwarding to prevent feedback loops.

## Requirements *(mandatory)*

### Architecture Intent

The log forwarding infrastructure introduced in this feature is transport-agnostic by design. Syslog is the first transport implementation. The queue mechanics, consumer interface, backpressure handling, and configuration schema are all designed so that future destination types (e.g., OpenTelemetry, webhooks, Redis) can be added as additional implementations without modifying the core event emission path or requiring administrators to restructure existing configuration. The `type` field on each destination is the extension point in the configuration layer; the `Event Consumer` interface is the extension point in the code.

### Functional Requirements

- **FR-001**: Administrators MUST be able to configure syslog export via the Infrahub configuration without requiring any code changes or additional software.
- **FR-002**: Each log forwarding destination configuration MUST include: a unique operator-supplied name, destination type, destination host/IP, port, transport protocol (TCP or UDP), syslog format (RFC 5424 or RFC 3164), and optional TLS settings. The name MUST be included in all observability output (log messages, warnings, connection state changes) so that operators can identify which destination is affected without ambiguity when multiple destinations are configured.
- **FR-003**: System MUST support configuring multiple independent log forwarding destinations within a single unified configuration section, each with its own independent settings.
- **FR-004**: System MUST emit syslog events for the following event types: user login, user logout, resource create, resource update, resource delete.
- **FR-005**: The syslog message (MSG field) for audit events MUST contain a JSON representation of the Infrahub event, including: user identity, timestamp, action type, resource type, resource identifier, branch context, and outcome. The JSON structure MUST be consistent with the event payload already emitted to Prefect so that operators can cross-reference events across both systems.
- **FR-006**: System MUST support both RFC 5424 and RFC 3164 syslog format standards, selectable per destination.
- **FR-007**: System MUST support both TCP and UDP as transport protocols for syslog delivery, selectable per destination.
- **FR-008**: System MUST support optional TLS encryption for TCP-based syslog connections.
- **FR-009**: System MUST deliver events in real-time (within 1 second of occurrence under normal conditions).
- **FR-010**: System MUST continue normal operation when a configured syslog destination is unavailable; the unavailability of syslog MUST NOT degrade Infrahub's core functionality or API response times.
- **FR-011**: Log forwarding MUST be fully decoupled from event production via a dedicated log forwarding service initialized at application startup. The service MUST expose a non-blocking enqueue interface called by the event pipeline and the logging infrastructure, so that network I/O to the log forwarding destination never executes on the API request path or any log-emitting call site.
- **FR-012**: Each log forwarding destination MUST have its own independent in-memory queue and its own dedicated consumer, so that a slow or unavailable destination does not affect event delivery to other destinations or to any other part of the event pipeline (message bus, Prefect).
- **FR-013**: The per-destination queue MUST be bounded. The maximum queue size MUST be configurable per destination (default: 10,000 entries). Drop behavior at enqueue time is determined by message type: when an incoming application log record arrives and the queue is full, the record is discarded without entering the queue; when an incoming audit event arrives and the queue is full, the oldest item currently in the queue is evicted to make room for the audit event. A warning MUST be written to Infrahub's own application logs on any discard or eviction.
- **FR-014**: TCP syslog connections MUST be persistent and reused across all messages for a given destination. Connections MUST have TCP keep-alive enabled to detect silently dropped connections caused by firewalls or NAT gateways.
- **FR-015**: On TCP connection loss, the syslog consumer MUST automatically attempt reconnection using exponential backoff. The maximum retry interval MUST be configurable (default: 60 seconds). Reconnection MUST happen without requiring an Infrahub restart.
- **FR-016**: The TCP framing method used when writing multiple messages over a persistent connection (newline-delimited or octet-counting per RFC 6587) MUST be configurable per destination to ensure compatibility with different syslog receivers.
- **FR-017**: On graceful shutdown, each destination consumer MUST attempt to drain its queue up to a configurable timeout (default: 10 seconds) before forcibly closing the connection.
- **FR-018**: UDP message payloads that exceed the maximum UDP datagram size MUST be truncated at the MSG field boundary. The truncated message MUST still be delivered and a warning MUST be written to Infrahub's application logs.
- **FR-019**: Syslog delivery failures, queue overflow events, and connection state changes MUST be written to Infrahub's own application logs, independently of and regardless of the health of the syslog destination.
- **FR-020**: Application log forwarding MUST be opt-in per destination and disabled by default. When enabled, a minimum severity level MUST be configurable per destination (default: WARNING). Log records below the configured minimum severity MUST be filtered before enqueuing and MUST NOT consume queue capacity.
- **FR-021**: The RFC 5424 FACILITY field MUST be set differently for audit events and application log records so that SIEM operators can filter or route the two streams independently at the syslog receiver without parsing message content. The FACILITY for audit events MUST be LOG_AUTH (facility code 4). The FACILITY for application log records MUST be LOG_LOCAL0 (facility code 16). These values are fixed across all Infrahub installations and are not operator-configurable, ensuring that SIEM integrations, documentation, and community-written parsers can rely on consistent field values regardless of deployment.
- **FR-022**: The RFC 5424 SEVERITY field for application log records MUST reflect the severity of the originating log message. The mapping from Infrahub log levels to RFC 5424 severity values MUST follow the standard correspondence (e.g., ERROR → Error, WARNING → Warning, INFO → Informational, DEBUG → Debug).
- **FR-023**: For RFC 5424 format, the APPNAME header field MUST be set to `infrahub`, the PROCID field MUST be set to the worker process identifier, and the MSGID field MUST be set to the event type name for audit events (e.g., `infrahub.node.created`) and to the nil value (`-`) for application log records. For RFC 3164 format, the TAG field MUST be set to `infrahub`.
- **FR-024**: Log messages emitted by the syslog service itself (e.g., delivery failure warnings, queue overflow warnings) MUST be excluded from application log forwarding to prevent feedback loops.
- **FR-025**: The event pipeline architecture MUST remain extensible, allowing future integrations (e.g., webhooks, message bus) to be added as additional consumers alongside syslog without modifying the core event emission logic.
- **FR-026**: Syslog export MUST be available as an enterprise edition feature; the underlying event pipeline architecture MUST be available in all editions.
- **FR-027**: All log forwarding destinations MUST be configured under a single, unified configuration namespace, regardless of destination type. Each destination MUST declare its type using a type field (e.g., `syslog`). This structure MUST allow future destination types to be introduced without requiring administrators to restructure or migrate existing destination configurations.

### Key Entities

- **Log Forwarding Destination**: A configured target for log forwarding, with attributes: name (unique identifier used in all observability output), type (in v1: `syslog`), host, port, transport protocol (TCP/UDP), syslog format (RFC 5424/RFC 3164), TCP framing method (newline/octet-counting), TLS enabled flag, optional TLS certificate path, queue size limit, maximum reconnection interval, shutdown drain timeout, application log forwarding enabled flag, and minimum log severity level.
- **Syslog Message**: The common envelope placed on the per-destination queue. Contains either an Audit Event or an Application Log Record, along with a message type discriminator used by the consumer to apply the correct format and RFC 5424 FACILITY value.
- **Audit Event**: A structured record of a tracked user action, with attributes: event type (login/logout/create/update/delete), user identity, timestamp, resource type, resource identifier, outcome (success/failure), and branch context. The serialized form is the JSON event payload already produced by the Infrahub event system.
- **Application Log Record**: A log message emitted by an Infrahub component, with attributes: logger name, severity level, message text, and timestamp. Sourced from Infrahub's logging infrastructure via a log handler that enqueues records meeting the configured minimum severity into the Syslog Service.
- **Syslog Service**: A long-lived service initialized at Infrahub startup that manages one queue and one consumer task per configured destination. Accepts both Audit Events and Application Log Records via a single non-blocking enqueue interface. Participates in the application startup and graceful shutdown lifecycle.
- **Event Consumer (extensibility interface)**: The abstract interface through which the event pipeline dispatches to sinks. The Syslog Service implements this interface. Designed so that future integrations (webhooks, custom event hooks) can be added as additional consumers without changes to the core emission logic.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Administrators can complete syslog configuration from a blank state by following the documentation.
- **SC-002**: All tracked audit events appear in the configured syslog destination within 1 second of occurrence under normal operating conditions.
- **SC-003**: Infrahub API response times are negligibly affected whether the syslog destination is available, unavailable, or slow.
- **SC-004**: Zero audit events are lost under normal operating conditions (syslog server available and responsive, queue not full).
- **SC-005**: Enqueueing a message into the syslog delivery pipeline adds no measurable latency to the call site.
- **SC-006**: After a TCP syslog server becomes reachable again following an outage, Infrahub resumes delivery automatically without operator intervention, within one reconnection backoff cycle.
- **SC-007**: Syslog messages are parseable by standard SIEM systems without requiring custom parsing rules beyond a single JSON field extraction from the syslog MSG field.
- **SC-008**: Enterprise customers with SOC2, ISO 27001, or equivalent compliance requirements can satisfy their audit log centralization obligation using this feature alone.
- **SC-009**: When application log forwarding is enabled with a minimum severity of WARNING, no DEBUG or INFO log records appear at the syslog destination under any operating condition.

## Assumptions

- Syslog delivery over UDP does not guarantee event delivery; this is an accepted trade-off for customers who prefer UDP on secured internal networks. For UDP destinations, Infrahub maintains no connection state, performs no startup reachability check, and applies no reconnection logic. UDP delivery is purely fire-and-forget.
- DNS resolution for TCP syslog destination hostnames is deferred to first connection attempt, not validated at startup. A hostname that is valid at startup may become unresolvable later, or vice versa; this is handled through the normal reconnection backoff mechanism. Syntactically invalid configuration values (e.g., port out of range) are the only configuration errors that prevent startup.
- Persistent buffering to disk for unavailable TCP destinations is deferred to a future release. The in-memory queue holds events during brief outages, but events are not recovered after a process restart or after the queue fills.
- In-memory queues are not persistent across process restarts. Messages pending in a worker's queue at the time of a crash or restart are lost. This is a known trade-off accepted for v1.
- Event ordering at the syslog destination is governed by the syslog timestamp on each message, not by Infrahub insertion order. Messages from concurrent requests served by different worker processes may arrive interleaved at the syslog server; the SIEM is responsible for ordering by timestamp.
- Each Infrahub worker process maintains its own independent syslog connection(s). The syslog server should be expected to handle one persistent TCP connection per active Infrahub worker process.
- Application log forwarding is disabled by default. When enabled, the default minimum severity of WARNING is expected to produce a volume low enough that application logs do not compete meaningfully with audit events for queue capacity.
- RFC 5424 STRUCTURED-DATA fields are not used in v1. All event and log data is placed in the MSG field. This maintains consistency with the payload format already used by the Prefect integration. STRUCTURED-DATA support may be added in a future release if specific SIEM integrations require it.
- Vendor-specific format templates or field mappings for individual SIEM products (e.g., Splunk HEC format, Datadog intake API) are out of scope for v1. The JSON MSG field is sufficient for ingestion by standard SIEM systems.
- This feature depends on INFP-474 (Add Login/Logout Activity Events) for authentication event types to be available in the event pipeline, but the feature in itself doesn't require INFP-474 to be implemented first.
- The internal log forwarding architecture (queue per destination, consumer task, backpressure, drain mechanics) is transport-agnostic by design. Syslog is the first transport implementation. Future releases may add alternative log forwarding destinations (e.g., Redis, RabbitMQ, OpenTelemetry) as additional transport implementations without requiring changes to the queue mechanics or the event emission path.

## Dependencies

- **INFP-474** – Add Login/Logout Activity Events: Required for login and logout events to be available in the audit event stream before they can be exported via syslog.
