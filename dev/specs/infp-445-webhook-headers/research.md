# Research: Custom HTTP Headers for Webhooks

**Feature**: INFP-445 | **Date**: 2026-03-11

## R1: Generic/Node Inheritance Pattern for New Entity Types

**Decision**: Follow the established `GenericSchema` + `NodeSchema(inherit_from=[...])` pattern used by `CoreTransformation`, `CoreWebhook`, `CoreAccount`, etc.

**Rationale**: The codebase has a well-established pattern for creating generic base types with specialized node implementations. This is how webhooks themselves are structured (`CoreWebhook` generic → `CoreStandardWebhook` / `CoreCustomWebhook` nodes). Using the same pattern for `CoreKeyValue` ensures consistency and leverages existing infrastructure (GraphQL generation, UI rendering, schema validation).

**Key findings**:
- Generic defined in `backend/infrahub/core/schema/definitions/core/` as `GenericSchema(...)` with `branch=BranchSupportType.AGNOSTIC`
- Node types use `inherit_from=[InfrahubKind.KEYVALUE]` to inherit generic attributes
- Registration in `core/__init__.py` under `core_models_mixed["generics"]` and `core_models_mixed["nodes"]`
- `InfrahubKind` constant must be added for the new generic

**Alternatives considered**:
- Single node type with a `type` dropdown attribute → Rejected: doesn't leverage schema-level type safety; Password kind attribute can't coexist with Text kind on the same schema
- Separate unrelated node types (no generic) → Rejected: can't define a single `headers` relationship on `CoreWebhook` pointing to all types

## R2: Password Attribute Kind Behavior

**Decision**: Use `kind="Password"` for the sensitive key-value pair value attribute. This is the existing `Password` data type (not `HashedPassword`).

**Rationale**: `Password` stores plaintext but masks in the UI/API via `_filter_sensitive()` returning `"***"`. This is what we need—the actual value must be available at send time for inclusion in HTTP headers. `HashedPassword` (bcrypt) would be irreversible and unusable for headers.

**Key findings**:
- `Password` kind: stored as plaintext `String` in Neo4j, masked as `"***"` in GraphQL responses when `filter_sensitive=True`
- Frontend: `PasswordDisplay` component with toggleable visibility; `PasswordInputField` for forms
- Changelog: `AttributeChangelog.filter_sensitive()` masks both current and previous values
- `CoreStandardWebhook.shared_key` already uses `kind="Password"` — exact same pattern

**Alternatives considered**:
- `HashedPassword` → Rejected: bcrypt hash is one-way; can't retrieve original value for HTTP headers
- Custom encryption at rest → Rejected: YAGNI for initial implementation; adds complexity without clear threat model improvement over existing Password behavior

## R3: Webhook Cache Extension for Headers

**Decision**: Extend the existing webhook cache serialization (`Webhook.to_cache()` / `Webhook.from_cache()`) to include resolved header key-value pairs. Add a `headers` field to the `Webhook` Pydantic model as `dict[str, HeaderConfig]`.

**Rationale**: The webhook process flow (`webhook_process` in `tasks/process.py`) already uses a 2-hour cache (`KVTTL.TWO_HOURS = 7200s`) keyed by `webhook:{webhook_id}`. Headers should be part of this cached data to avoid extra DB queries on every webhook fire. Since `to_cache()` calls `model_dump()`, adding headers as a Pydantic field automatically includes them in serialization.

**Key findings**:
- Cache key: `webhook:{webhook_id}` in NATS KV
- `convert_node_to_webhook()` task fetches from DB on cache miss → must also fetch headers here
- `Webhook.to_cache()` → `self.model_dump()` → JSON serialized to NATS
- `Webhook.from_cache()` → `cls(**data)` → Pydantic model from dict
- Cache invalidation: `cache.delete(key=f"webhook:{webhook.id}")` in `_configure_one()` and `_delete_automation()`

**Alternatives considered**:
- Separate cache for headers → Rejected: adds complexity, requires coordinated invalidation, no benefit
- No caching (always fetch headers from DB) → Rejected: adds DB query on every webhook fire; inconsistent with existing caching strategy

## R4: Cache Invalidation for Header Changes

**Decision**: Extend the webhook-configure trigger to also fire when `CoreKeyValue*` nodes are created/updated/deleted, and when the headers relationship changes. The trigger invalidates the relevant webhook cache entries.

**Rationale**: The existing `TRIGGER_WEBHOOK_CONFIGURE` watches for `infrahub.node.created/updated/deleted` on `CoreStandardWebhook` and `CoreCustomWebhook`. For header changes, we need to invalidate the cache of all webhooks linked to the changed key-value pair. Two scenarios:
1. **Key-value node change** (value updated): must invalidate all linked webhooks' caches
2. **Relationship change** (header linked/unlinked from webhook): must invalidate the affected webhook's cache

**Key findings**:
- `TRIGGER_WEBHOOK_CONFIGURE` in `webhook/triggers.py` matches on `infrahub.node.kind` for webhook types
- Relationship changes emit `infrahub.relationship.created/deleted` events
- The configure flow's `_configure_one()` already calls `cache.delete()`
- Adding key-value kinds to the trigger match and handling relationship events covers both scenarios

**Alternatives considered**:
- Rely solely on 2-hour TTL expiration → Rejected: stale headers for up to 2 hours is unacceptable for credential rotation
- Webhook-side polling for header freshness → Rejected: adds latency and complexity

## R5: Environment Variable Resolution Strategy

**Decision**: Resolve environment variables via `os.environ.get()` at webhook send time in the `_assign_headers()` method (or a new `_resolve_custom_headers()` method) within the Prefect worker process.

**Rationale**: Environment variables must be resolved where the webhook HTTP request is made—on the Prefect worker. The spec explicitly states resolution at send time, not configuration time. This means env var values are NOT cached; only the env var name is cached.

**Key findings**:
- `Webhook.prepare()` → `_assign_headers()` runs in the Prefect worker context
- Worker pods in Kubernetes have env vars injected by operators (Vault, K8s secrets)
- `os.environ.get()` is synchronous and negligible cost

**Design**:
- Cache stores: `{"type": "env", "key": "Authorization", "value": "MY_AUTH_TOKEN_VAR"}`
- At send time: `os.environ.get("MY_AUTH_TOKEN_VAR")` → actual value or `None` (skip + warn)

**Alternatives considered**:
- Resolve at cache-write time → Rejected: violates spec requirement FR-008; stale for up to 2 hours
- Use a secrets manager SDK → Rejected: YAGNI; env var injection is the standard K8s pattern

## R6: Many-to-Many Relationship Pattern

**Decision**: Define a `headers` relationship on `CoreWebhook` generic with `cardinality=Cardinality.MANY`, `kind=RelKind.GENERIC`, `optional=True`, pointing to `InfrahubKind.KEYVALUE`.

**Rationale**: Defining the relationship on the generic means both `CoreStandardWebhook` and `CoreCustomWebhook` inherit it automatically. `RelKind.GENERIC` allows the peer to be any node that implements the `CoreKeyValue` generic. Many-to-many is the default when both sides have `cardinality=MANY`.

**Key findings**:
- Existing pattern: `CoreCustomWebhook` has `transformation` relationship to `CoreTransformPython` with `cardinality=Cardinality.ONE`
- Generic relationships: `CoreGenericRepository` has `tags` relationship with `cardinality=Cardinality.MANY`
- `RelKind.GENERIC` is used when the peer is a generic (vs `RelKind.ATTRIBUTE` for concrete nodes)

**Alternatives considered**:
- Define relationship on each webhook node type separately → Rejected: duplicates configuration; violates DRY; spec says "defined on this webhook generic"
- Use `RelKind.ATTRIBUTE` → Incorrect: peer is a generic, not a specific node type

## R7: Header Name Validation

**Decision**: Validate HTTP header names conform to RFC 7230 (visible ASCII characters excluding delimiters). Validate environment variable names match `^[A-Za-z_][A-Za-z0-9_]*$`.

**Rationale**: Invalid header names would cause HTTP client errors at send time. Validating at creation time provides better user experience. Environment variable names have OS-level constraints.

**Key findings**:
- `httpx` (used by `InfrahubHTTP`) validates header names but raises low-level errors
- Infrahub uses Pydantic models at API boundaries for input validation
- The `Attr` definition supports `regex` for pattern validation

**Alternatives considered**:
- No validation (let httpx fail) → Rejected: poor error messages; fails at send time instead of creation time
- Strict IANA-registered header names only → Rejected: too restrictive; custom `X-*` headers are common
