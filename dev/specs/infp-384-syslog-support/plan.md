# Implementation Plan: Syslog Support for Infrahub

**Feature Branch**: `infp-384-syslog-support`
**Spec**: [spec.md](spec.md)
**Created**: 2026-03-17
**Updated**: 2026-03-17

---

## Repository Structure

This feature spans two codebases that live in a single monorepo:

- **Community repo** (git submodule): `community/` — the open-source `infrahub` package
  - Backend code: `community/backend/infrahub/`
  - Tests: `community/backend/tests/`
- **Enterprise repo** (parent): root of `infrahub-private`
  - Backend code: `enterprise/backend/infrahub_enterprise/`
  - Tests: `enterprise/backend/tests/enterprise_unit/`, `enterprise_backend/tests/enterprise_component/`, `enterprise/backend/tests/enterprise_functional/`

The enterprise entry point (`enterprise/backend/infrahub_enterprise/server.py`) imports the community app and applies dependency overrides via `set_enterprise_dependencies()` at import time.

---

## Community / Enterprise Split

The community repo provides interfaces, configuration models, and integration hooks. The enterprise repo provides the concrete syslog implementation. This follows the established `ApprovalRevoker` / `ApprovalRevokerEnt` pattern with `fast_depends` `dependency_provider.override()`.

| Layer | Community (`community/backend/infrahub/`) | Enterprise (`enterprise/backend/infrahub_enterprise/`) |
|-------|-------------------------------------------|-------------------------------------------------------|
| Configuration | `LogForwardingSettings`, `LogForwardingDestination`, enums, validators in `config.py` | — |
| Enterprise gate | `EnterpriseFeatures.LOG_FORWARDING_SYSLOG` + `_validate_feature_selection()` | — |
| Interfaces | `LogForwardingService` ABC, `EventConsumer` protocol, `SyslogMessage` model | — |
| Community stub | `LogForwardingServiceCommunity` (no-op) + `get_log_forwarding_service()` factory | — |
| Dependency injection | `get_log_forwarding_service()` in `workers/dependencies.py` | `get_ent_log_forwarding_service()` + `dependency_provider.override()` in `enterprise.py` |
| Event integration | `InfrahubEventService` dispatches to log forwarding service (via interface) | — |
| Service lifecycle | `InfrahubServices._log_forwarding` field, wired into `new()` and `shutdown()` | — |
| RFC 5424/3164 formatters | — | `format_rfc5424()`, `format_rfc3164()` |
| Transport (TCP/UDP/TLS) | — | `TcpTransport`, `UdpTransport` |
| Consumer & queue | — | `SyslogConsumer`, priority queue with eviction |
| Concrete service | — | `LogForwardingServiceEnt` |
| App log handler | — | `SyslogLogHandler(logging.Handler)` |

---

## Technical Context

### Codebase Integration Points

| Concern | Current State | Integration Strategy |
|---------|---------------|---------------------|
| Configuration | Pydantic `BaseSettings` in `community/backend/infrahub/config.py`, TOML-based | Add `LogForwardingSettings` section with per-destination list |
| Enterprise gate | `EnterpriseFeatures` enum + `PolicySettings.enterprise_features` property + `_validate_feature_selection()` in `server.py` | Add `LOG_FORWARDING_SYSLOG` variant; detect via presence of `log_forwarding.destinations` with `type = "syslog"` |
| Event emission | `InfrahubEventService.send()` in `community/backend/infrahub/services/adapters/event/__init__.py` dispatches to Prefect + message bus via `asyncio.gather()` | Add third dispatch target: `_send_log_forwarding()` using injected `LogForwardingService` |
| Application logging | structlog via `log.py`, no custom handlers | Enterprise adds `logging.Handler` that enqueues to log forwarding service |
| Service lifecycle | `InfrahubServices` in `community/backend/infrahub/services/__init__.py` with `new()` factory + `shutdown()` | Add `_log_forwarding` optional field, init via DI in `server.py`, drain on shutdown |
| TLS | `HTTPSettings.get_tls_context()` pattern with CA bundle | Enterprise reuses same pattern for syslog TLS config |
| Worker processes | Each gunicorn worker runs `app_initialization()` independently | Each worker gets its own syslog service + connections (per spec assumption) |
| Dependency injection | `fast_depends` `dependency_provider.override()` in `enterprise/backend/infrahub_enterprise/enterprise.py` overrides community factory functions | Add `get_log_forwarding_service()` in community, override with `get_ent_log_forwarding_service()` in enterprise |

### Key Design Decisions

1. **No external syslog library** — RFC 5424/3164 formatting is simple enough to implement directly; avoids dependency for a ~100-line formatter.
2. **asyncio.Queue per destination** — matches existing async patterns (NATS, RabbitMQ adapters). Bounded queue with `maxsize`.
3. **Background asyncio.Task per destination** — consumer loop reads from queue, writes to socket. Follows the `InfrahubScheduler` pattern.
4. **Fire-and-forget enqueue** — `enqueue()` is non-blocking, never awaits network I/O. Matches FR-011.
5. **ABC + community stub + fast_depends override** — follows `ApprovalRevoker`/`ApprovalRevokerEnt` pattern. Community defines `get_log_forwarding_service()` returning the no-op stub; enterprise overrides via `dependency_provider.override()` in `set_enterprise_dependencies()`.

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Infrahub Worker Process                                        │
│                                                                 │
│  ┌──────────────┐    ┌──────────────────┐                       │
│  │ GraphQL      │───►│ InfrahubEvent    │                       │
│  │ Mutations    │    │ Service.send()   │                       │
│  └──────────────┘    └───────┬──────────┘                       │
│                              │                                  │
│                    ┌─────────┼──────────┐                       │
│                    ▼         ▼          ▼                       │
│              ┌─────────┐ ┌────────┐ ┌──────────────────┐        │
│              │ Prefect │ │ Msg    │ │ LogForwarding    │        │
│              │ Events  │ │ Bus    │ │ Service (ABC)    │        │
│              └─────────┘ └────────┘ │                  │        │
│                                     │  enqueue(msg)    │        │
│  ┌──────────────┐                   │       │          │        │
│  │ Python       │──►LogHandler──────┤       ▼          │        │
│  │ Logging      │  (enterprise)     │  ┌──────────┐    │        │
│  └──────────────┘                   │  │ Dest 1   │    │        │
│                                     │  │ Queue    │───►│ TCP/UDP│
│                                     │  └──────────┘    │ Socket │
│                                     │  ┌──────────┐    │        │
│                                     │  │ Dest 2   │    │        │
│                                     │  │ Queue    │───►│ TCP/UDP│
│                                     │  └──────────┘    │ Socket │
│                                     └──────────────────┘        │
│                                      ▲ enterprise impl          │
│  COMMUNITY (community/backend/infrahub/) ───────────────────────│
│  Interfaces, config, event dispatch, DI factory                 │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
│  ENTERPRISE (enterprise/backend/infrahub_enterprise/)           │
│  Formatters, transport, consumer,                               │
│  LogForwardingServiceEnt, DI override                           │
└─────────────────────────────────────────────────────────────────┘
```

### Module Layout

**Community repo** (`community/backend/infrahub/log_forwarding/`):
```
community/backend/infrahub/log_forwarding/
├── __init__.py              # LogForwardingService ABC + LogForwardingServiceCommunity stub
└── models.py                # SyslogMessage, MessageType enum (shared data types)
```

**Enterprise repo** (`enterprise/backend/infrahub_enterprise/log_forwarding/`):
```
enterprise/backend/infrahub_enterprise/log_forwarding/
├── __init__.py              # LogForwardingServiceEnt
├── dependencies.py          # get_ent_log_forwarding_service() factory
├── consumer.py              # SyslogConsumer (per-destination queue + consumer loop)
├── formatter.py             # RFC 5424 / RFC 3164 formatters
├── handler.py               # SyslogLogHandler(logging.Handler) for app log forwarding
└── transport.py             # TcpTransport, UdpTransport (with TLS, keep-alive, backoff)
```

---

## Data Model

### Configuration Schema (TOML)

```toml
[[log_forwarding.destinations]]
name = "siem-primary"
type = "syslog"
host = "syslog.example.com"
port = 514
protocol = "tcp"                    # tcp | udp
format = "rfc5424"                  # rfc5424 | rfc3164
tcp_framing = "newline"             # newline | octet-counting
tls_enabled = false
tls_ca_bundle = ""                  # path or PEM string (optional)
queue_size = 10000
max_reconnect_interval = 60         # seconds
shutdown_drain_timeout = 10         # seconds
forward_application_logs = false
min_log_severity = "WARNING"        # DEBUG | INFO | WARNING | ERROR | CRITICAL
```

### Pydantic Models (community repo — `community/backend/infrahub/config.py`)

```python
class SyslogProtocol(StrEnum):
    TCP = "tcp"
    UDP = "udp"

class SyslogFormat(StrEnum):
    RFC5424 = "rfc5424"
    RFC3164 = "rfc3164"

class TcpFraming(StrEnum):
    NEWLINE = "newline"
    OCTET_COUNTING = "octet-counting"

class LogForwardingDestination(BaseSettings):
    name: str                                    # unique, used in all log output
    type: Literal["syslog"]                      # extensible for future types
    host: str
    port: int = Field(ge=1, le=65535)
    protocol: SyslogProtocol = SyslogProtocol.TCP
    format: SyslogFormat = SyslogFormat.RFC5424
    tcp_framing: TcpFraming = TcpFraming.NEWLINE
    tls_enabled: bool = False
    tls_ca_bundle: str | None = None
    queue_size: int = Field(default=10000, ge=1)
    max_reconnect_interval: int = Field(default=60, ge=1)
    shutdown_drain_timeout: int = Field(default=10, ge=0)
    forward_application_logs: bool = False
    min_log_severity: str = "WARNING"

class LogForwardingSettings(BaseSettings):
    destinations: list[LogForwardingDestination] = Field(default_factory=list)

    @field_validator("destinations")
    def validate_unique_names(cls, v):
        names = [d.name for d in v]
        if len(names) != len(set(names)):
            raise ValueError("Destination names must be unique")
        return v
```

### Internal Message Model (community repo — `community/backend/infrahub/log_forwarding/models.py`)

```python
class MessageType(StrEnum):
    AUDIT_EVENT = "audit_event"
    APPLICATION_LOG = "application_log"

class SyslogMessage(BaseModel):
    message_type: MessageType
    timestamp: datetime
    payload: str                  # JSON for audit events, text for app logs
    event_type: str | None        # e.g. "infrahub.node.created" (audit only)
    severity: int                 # RFC 5424 severity code
    facility: int                 # 4 = LOG_AUTH (audit), 16 = LOG_LOCAL0 (app)
    process_id: str               # worker identity
```

---

## Contracts

### LogForwardingService ABC (community repo — `community/backend/infrahub/log_forwarding/__init__.py`)

```python
class LogForwardingService(ABC):
    """Abstract base for log forwarding. Enterprise provides concrete implementation."""

    @abstractmethod
    async def start(self) -> None:
        """Start consumer tasks for all destinations."""

    @abstractmethod
    def enqueue(self, message: SyslogMessage) -> None:
        """Non-blocking. Applies drop/eviction policy per FR-013. Never raises."""

    @abstractmethod
    async def shutdown(self, timeout: float | None = None) -> None:
        """Signal consumers to drain queues, wait up to timeout, then force close."""


class LogForwardingServiceCommunity(LogForwardingService):
    """No-op stub for community edition. No destinations are ever configured
    (enterprise gate prevents it), so all methods are no-ops."""

    async def start(self) -> None:
        pass

    def enqueue(self, message: SyslogMessage) -> None:
        pass

    async def shutdown(self, timeout: float | None = None) -> None:
        pass
```

### Dependency Injection (community + enterprise)

```python
# Community: community/backend/infrahub/workers/dependencies.py
# Decorated with @inject so fast_depends can resolve it
def get_log_forwarding_service() -> LogForwardingService:
    """Default factory — returns community no-op stub."""
    return LogForwardingServiceCommunity()

# Enterprise: enterprise/backend/infrahub_enterprise/log_forwarding/dependencies.py
def get_ent_log_forwarding_service() -> LogForwardingService:
    """Enterprise factory — returns concrete service built from config."""
    destinations = config.SETTINGS.log_forwarding.destinations
    if not destinations:
        return LogForwardingServiceCommunity()
    return LogForwardingServiceEnt(destinations)

# Enterprise: enterprise/backend/infrahub_enterprise/enterprise.py
# Added to set_enterprise_dependencies():
dependency_provider.override(get_log_forwarding_service, get_ent_log_forwarding_service)
```

### EventConsumer Protocol (community repo, extensibility point per FR-025)

```python
class EventConsumer(Protocol):
    """Abstract consumer interface for the event pipeline."""

    def enqueue(self, message: SyslogMessage) -> None: ...
    async def start(self) -> None: ...
    async def shutdown(self, timeout: float | None = None) -> None: ...
```

### SyslogConsumer (enterprise repo, per-destination)

```python
class SyslogConsumer:
    """One instance per configured destination. Owns queue + transport."""

    def __init__(self, destination: LogForwardingDestination) -> None: ...

    async def run(self) -> None:
        """Main consumer loop: dequeue -> format -> send. Handles reconnection."""

    async def drain(self, timeout: float) -> None:
        """Drain remaining queue items within timeout on shutdown."""
```

### Transport Interface (enterprise repo)

```python
class SyslogTransport(Protocol):
    async def connect(self) -> None: ...
    async def send(self, data: bytes) -> None: ...
    async def close(self) -> None: ...
    @property
    def is_connected(self) -> bool: ...

class TcpTransport(SyslogTransport):
    """Persistent TCP with keep-alive, optional TLS, reconnection backoff."""

class UdpTransport(SyslogTransport):
    """Fire-and-forget UDP. No connection state."""
```

---

## Implementation Phases

### Phase 1: Configuration & Enterprise Gate (community repo)

**Files to modify:**
- `community/backend/infrahub/config.py` — Add `SyslogProtocol`, `SyslogFormat`, `TcpFraming` enums, `LogForwardingDestination`, `LogForwardingSettings` models, `LOG_FORWARDING_SYSLOG` to `EnterpriseFeatures` enum, `log_forwarding: LogForwardingSettings` field to `Settings`
- `community/backend/infrahub/server.py` — `_validate_feature_selection()` already handles `EnterpriseFeatures`; the new variant is detected automatically via `enterprise_features` property

**Enterprise gate mechanism:**
- Add a `log_forwarding` property to `Settings` (or `ConfiguredSettings`) similar to `enterprise_features`
- `PolicySettings.enterprise_features` property returns features based on config values; for log forwarding, detect `LOG_FORWARDING_SYSLOG` when any destination has `type = "syslog"`
- Alternatively, put the enterprise feature detection on `LogForwardingSettings` itself and aggregate into the existing `enterprise_features` property on `Settings`
- `_validate_feature_selection()` in `server.py` already rejects any `EnterpriseFeatures` in community edition — no new code needed there

**Files to create:**
- `community/backend/infrahub/log_forwarding/__init__.py` — `LogForwardingService` ABC + `LogForwardingServiceCommunity` stub
- `community/backend/infrahub/log_forwarding/models.py` — `SyslogMessage`, `MessageType`

**Tests** (`community/backend/tests/unit/`):
- Config validation: valid TOML parses, invalid port rejects, duplicate names reject
- Enterprise gate: community edition rejects syslog config, enterprise allows it
- Empty destinations list: no error, no syslog service started
- Community stub: `enqueue()` and `shutdown()` are no-ops

**Exit criteria:** `infrahub.toml` with `[[log_forwarding.destinations]]` loads and validates; community edition rejects it; empty config is a no-op.

---

### Phase 2: Interfaces & Event Integration (community repo)

**Files to modify:**
- `community/backend/infrahub/services/__init__.py` — Add `_log_forwarding: LogForwardingService | None` optional field to `InfrahubServices`, add to `__init__()` and `new()`, wire `shutdown()` to call `await _log_forwarding.shutdown()`
- `community/backend/infrahub/services/adapters/event/__init__.py` — Add `log_forwarding: LogForwardingService | None` parameter to `InfrahubEventService.__init__()`, add `_send_log_forwarding()` method, include it in `send()`'s `asyncio.gather()` tasks
- `community/backend/infrahub/server.py` — In `app_initialization()`, resolve log forwarding service via DI (`get_log_forwarding_service()`), pass to `InfrahubServices.new()`, call `await service.start()`
- `community/backend/infrahub/workers/dependencies.py` — Add `get_log_forwarding_service()` factory function

**Event integration:**
- `InfrahubEventService.__init__()` gets optional `log_forwarding: LogForwardingService | None` parameter
- `send()` adds `_send_log_forwarding()` to the `asyncio.gather()` tasks
- `_send_log_forwarding()` converts `InfrahubEvent` -> `SyslogMessage` and calls `enqueue()`
- Conversion extracts: `event.event_name`, `event.get_event_payload()` (JSON), account_id, timestamp, branch

**Lifecycle:**
- `app_initialization()`: resolve service via DI (`get_log_forwarding_service`), call `await service.start()`
- `InfrahubServices.shutdown()`: call `await _log_forwarding.shutdown()`

**Tests** (`community/backend/tests/unit/`):
- Event emission calls `enqueue()` on the log forwarding service
- No enqueue when community stub is used (no-op)
- `InfrahubEvent` -> `SyslogMessage` conversion produces correct fields
- Event payload matches Prefect payload format (FR-005)
- Shutdown calls `log_forwarding.shutdown()`

**Exit criteria:** Community repo has all hooks in place; enterprise repo can inject an implementation via `dependency_provider.override()` and receive events.

---

### Phase 3: RFC 5424/3164 Formatters (enterprise repo)

**Files to create:**
- `enterprise/backend/infrahub_enterprise/log_forwarding/formatter.py` — `format_rfc5424()`, `format_rfc3164()`

**Key behavior:**
- RFC 5424: `<PRI>1 TIMESTAMP HOSTNAME infrahub PROCID MSGID - MSG`
- RFC 3164: `<PRI>TIMESTAMP HOSTNAME infrahub: MSG`
- PRI = facility * 8 + severity
- FACILITY: `LOG_AUTH` (4) for audit events, `LOG_LOCAL0` (16) for app logs (FR-021)
- MSGID: event type name for audit events, `-` for app logs (FR-023)
- MSG: JSON payload for audit events, text for app logs

**Tests** (`enterprise/backend/tests/enterprise_unit/`):
- RFC 5424 output matches standard format
- RFC 3164 output matches standard format
- PRI calculation correct for all facility/severity combinations
- APPNAME, PROCID, MSGID set correctly per FR-023

**Exit criteria:** Formatter produces valid syslog messages that parse in standard syslog receivers.

---

### Phase 4: Transport Layer (enterprise repo)

**Files to create:**
- `enterprise/backend/infrahub_enterprise/log_forwarding/transport.py` — `TcpTransport`, `UdpTransport`

**TcpTransport behavior:**
- `asyncio.open_connection()` with optional `ssl` context
- TCP keep-alive enabled (FR-014)
- Exponential backoff reconnection (FR-015), configurable max interval
- Newline-delimited or octet-counting framing per FR-016
- Connection errors logged, never raised to caller

**UdpTransport behavior:**
- `asyncio.DatagramProtocol` or raw `socket.socket` with `SOCK_DGRAM`
- No connection state (fire-and-forget)
- Truncate at MSG boundary if payload exceeds max UDP datagram size (FR-018)

**TLS:**
- Reuse `HTTPSettings.get_tls_context()` pattern
- CA bundle validation on `LogForwardingDestination` model validator
- TLS only valid with TCP (validator rejects TLS + UDP)

**Tests** (`enterprise/backend/tests/enterprise_unit/`):
- TCP connects, sends, receives acknowledgment
- TCP reconnects on connection drop with backoff
- TCP keep-alive is enabled on socket
- UDP sends without connection state
- TLS handshake succeeds with valid cert, fails gracefully with invalid
- Octet-counting frames correctly (`<len> <msg>`)
- UDP truncation at MSG boundary

**Exit criteria:** Both transports reliably deliver messages and handle failures gracefully.

---

### Phase 5: Consumer, Queue & Concrete Service (enterprise repo)

**Files to create:**
- `enterprise/backend/infrahub_enterprise/log_forwarding/consumer.py` — `SyslogConsumer`
- `enterprise/backend/infrahub_enterprise/log_forwarding/__init__.py` — `LogForwardingServiceEnt`
- `enterprise/backend/infrahub_enterprise/log_forwarding/dependencies.py` — `get_ent_log_forwarding_service()` factory

**Files to modify:**
- `enterprise/backend/infrahub_enterprise/enterprise.py` — Add `dependency_provider.override(get_log_forwarding_service, get_ent_log_forwarding_service)` to `set_enterprise_dependencies()`

**Queue behavior (FR-013):**
- `asyncio.Queue(maxsize=queue_size)` per destination
- Custom enqueue logic:
  - App log + queue full -> discard immediately, log warning
  - Audit event + queue full -> evict oldest item, enqueue new event, log warning
- This requires a custom queue wrapper since `asyncio.Queue` doesn't support eviction

**Consumer loop:**
- `while running: msg = await queue.get() -> format(msg) -> transport.send(formatted)`
- On transport error: hold message, attempt reconnect, retry
- On shutdown signal: switch to drain mode with timeout (FR-017)

**LogForwardingServiceEnt:**
- Implements `LogForwardingService` ABC
- Creates one `SyslogConsumer` per destination
- `enqueue()` fans out to all consumer queues
- `start()` launches consumer tasks
- `shutdown()` signals consumers to drain within per-destination timeout

**Enterprise DI registration:**
- `get_ent_log_forwarding_service()` reads `config.SETTINGS.log_forwarding.destinations`, returns `LogForwardingServiceEnt(destinations)` or `LogForwardingServiceCommunity()` if no destinations
- `set_enterprise_dependencies()` in `enterprise.py` overrides `get_log_forwarding_service` with `get_ent_log_forwarding_service`

**Tests** (`enterprise/backend/tests/enterprise_unit/`):
- Consumer dequeues and sends messages
- Queue eviction policy: audit events evict oldest, app logs are dropped
- Drain on shutdown respects timeout
- Consumer continues after transport reconnection
- Warning logged on every drop/eviction
- Full service: enqueue -> format -> transport -> delivered

**Exit criteria:** Enterprise service reliably processes events from enqueue through to syslog delivery.

---

### Phase 6: Application Log Forwarding (enterprise repo)

**Files to create:**
- `enterprise/backend/infrahub_enterprise/log_forwarding/handler.py` — `SyslogLogHandler(logging.Handler)`

**Handler behavior:**
- Standard Python `logging.Handler` subclass
- Attached to root logger during enterprise service `start()`
- Filters by destination's `min_log_severity`
- Converts `LogRecord` -> `SyslogMessage` with `MessageType.APPLICATION_LOG`
- Calls `LogForwardingServiceEnt.enqueue()` (non-blocking)
- Excludes log records from `infrahub.log_forwarding.*` and `infrahub_enterprise.log_forwarding.*` loggers (FR-024, feedback loop prevention)

**Severity mapping (FR-022):**
- Python `CRITICAL` -> RFC 5424 severity 2 (Critical)
- Python `ERROR` -> RFC 5424 severity 3 (Error)
- Python `WARNING` -> RFC 5424 severity 4 (Warning)
- Python `INFO` -> RFC 5424 severity 6 (Informational)
- Python `DEBUG` -> RFC 5424 severity 7 (Debug)

**Tests** (`enterprise/backend/tests/enterprise_unit/`):
- Handler filters below min severity
- Handler forwards at/above min severity
- Feedback loop prevention: log_forwarding logger messages excluded
- Disabled by default (no handler attached unless `forward_application_logs=True`)
- App logs use LOG_LOCAL0 facility, audit events use LOG_AUTH

**Exit criteria:** Application logs forwarded per configuration, no feedback loops, correct severity mapping.

---

### Phase 7: E2E Testing (enterprise repo)

**E2E test scenarios** (`enterprise/backend/tests/enterprise_functional/` or `enterprise_component/`):
- Single TCP destination: create object -> verify syslog message received
- Single UDP destination: create object -> verify syslog message received
- TLS destination: verify TLS handshake and encrypted delivery
- Multiple destinations: verify both receive events
- Destination down: verify Infrahub operates normally, events queue
- Destination recovery: verify automatic reconnection and delivery resumes
- Queue overflow: verify audit events evict oldest, app logs dropped
- Graceful shutdown: verify queue drain within timeout
- RFC 5424 format validation against standard parser
- RFC 3164 format validation against standard parser
- Community edition: verify syslog config rejected at startup

**Exit criteria:** Full end-to-end syslog delivery working across all configured scenarios.

---

## Implementation Order & Dependencies

```
COMMUNITY REPO (community/backend/infrahub/):
  Phase 1: Configuration & Gate ──► Phase 2: Interfaces & Event Integration

ENTERPRISE REPO (enterprise/backend/infrahub_enterprise/):
  Phase 3: Formatters ────────────► Phase 5: Consumer/Queue/Service
                                    ▲
  Phase 4: Transport ───────────────┘
                                    │
                                    ▼
                             Phase 6: App Log Forwarding
                                    │
                                    ▼
                             Phase 7: E2E Testing
```

Phases 1 and 2 are sequential (community repo). Phases 3 and 4 can proceed in parallel (enterprise repo). Phase 5 depends on 3 and 4. Phases 6 and 7 are sequential after 5.

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Queue memory under high load | Bounded queue (default 10k), drop policy, configurable per destination |
| TCP reconnection storms | Exponential backoff with configurable max interval |
| Feedback loops in app log forwarding | Exclude `*log_forwarding*` logger namespaces |
| Blocking API on syslog I/O | All network I/O in consumer tasks, enqueue is non-blocking |
| UDP message truncation | Truncate at MSG boundary, log warning (FR-018) |
| TLS misconfiguration at startup | Validate CA bundle in Pydantic model validator, fail fast |
| Community/enterprise interface mismatch | ABC in community repo enforces contract; enterprise tests import community interfaces |

---

## Out of Scope (v1)

- Mutual TLS (mTLS)
- RFC 5424 STRUCTURED-DATA
- Persistent/disk-backed queues
- Vendor-specific SIEM formats (Splunk HEC, Datadog)
- Login/logout events (depends on INFP-474, can be added independently)
- Denied permission events

---

## Task Breakdown

Parent: IFC-2270

| # | Summary | Phase | Repo | Blocked By | Description |
|---|---------|-------|------|------------|-------------|
| 1 | Log forwarding config models & enterprise gate | Phase 1 | Community | — | Add `LogForwardingSettings`, `LogForwardingDestination`, enums to `config.py`; add `LOG_FORWARDING_SYSLOG` to `EnterpriseFeatures`; wire into `_validate_feature_selection()`. Tests: valid/invalid TOML parsing, enterprise gate rejection, empty destinations no-op. |
| 2 | LogForwardingService ABC & community stub | Phase 1 | Community | — | Create `log_forwarding/` package with `LogForwardingService` ABC, `LogForwardingServiceCommunity` no-op stub, `SyslogMessage` and `MessageType` models. Tests: stub no-op behavior. |
| 3 | Event integration & service lifecycle hooks | Phase 2 | Community | 1, 2 | Add `_send_log_forwarding()` to `InfrahubEventService.send()`, wire `LogForwardingService` into `InfrahubServices` lifecycle (start/shutdown), add `get_log_forwarding_service()` DI factory. Tests: event->SyslogMessage conversion, enqueue on dispatch, payload matches Prefect format (FR-005), shutdown propagation. |
| 4 | RFC 5424 syslog formatter | Phase 3 | Enterprise | 2 | Implement `format_rfc5424()` with correct PRI, FACILITY, APPNAME, PROCID, MSGID per FR-021/FR-023. Tests: format validation, PRI calculation, header fields. |
| 5 | RFC 3164 syslog formatter | Phase 3 | Enterprise | 2 | Implement `format_rfc3164()` with correct PRI, FACILITY, TAG per FR-021/FR-023. Tests: format validation, PRI calculation, TAG field. |
| 6 | TCP transport | Phase 4 | Enterprise | — | `TcpTransport` with persistent connection, TCP keep-alive (FR-014), exponential backoff reconnection (FR-015), newline/octet-counting framing (FR-016), optional TLS (FR-008). Tests: connect/reconnect/keep-alive, TLS handshake, octet-counting framing. |
| 7 | UDP transport | Phase 4 | Enterprise | — | `UdpTransport` with fire-and-forget delivery, MSG-boundary truncation for oversized datagrams (FR-018). Tests: send without connection state, truncation behavior. |
| 8 | Bounded queue with eviction policy | Phase 5 | Enterprise | — | Custom async queue wrapper: bounded per-destination, app logs discarded when full, audit events evict oldest (FR-013). Tests: eviction policy, drop warnings logged. |
| 9 | SyslogConsumer per-destination loop | Phase 5 | Enterprise | 4, 5, 6, 7, 8 | Consumer loop: dequeue -> format -> transport.send, reconnection retry on transport error, drain mode with configurable timeout on shutdown (FR-017). Tests: dequeue-and-send, reconnection continuity, drain timeout. |
| 10 | LogForwardingServiceEnt & DI wiring | Phase 5 | Enterprise | 3, 9 | Concrete `LogForwardingServiceEnt` implementing the ABC: creates one `SyslogConsumer` per destination, fan-out enqueue, start/shutdown lifecycle. `get_ent_log_forwarding_service()` factory in `dependencies.py`, `dependency_provider.override()` in `enterprise.py`. Tests: full enqueue-to-delivery flow, multi-destination fan-out. |
| 11 | Application log forwarding handler | Phase 6 | Enterprise | 10 | `SyslogLogHandler(logging.Handler)` with severity filtering (FR-020), feedback loop prevention (FR-024), severity mapping (FR-022). Attached to root logger during service start. Tests: severity filtering, feedback loop exclusion, disabled-by-default, correct FACILITY per message type. |
| 12 | E2E integration tests | Phase 7 | Enterprise | 10, 11 | TCP/UDP/TLS delivery, multi-destination, destination failure/recovery, queue overflow, graceful shutdown drain, RFC format validation, community gate rejection. |
