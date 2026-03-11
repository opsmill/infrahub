# Data Model: Custom HTTP Headers for Webhooks

**Feature**: INFP-445 | **Date**: 2026-03-11

## Entities

### CoreKeyValue (Generic)

Base generic for reusable key-value configuration objects.

| Field | Type | Kind | Required | Unique | Notes |
|-------|------|------|----------|--------|-------|
| `name` | Text | Text | Yes | Yes (global) | Human-friendly identifier; globally unique across all KV types via generic `uniqueness_constraints` |
| `key` | Text | Text | Yes | No | The key name (e.g., HTTP header field name like `Authorization`) |
| `description` | Text | Text | No | No | Optional description |

**Schema properties**:
- `branch`: `BranchSupportType.AGNOSTIC` (matches webhook behavior)
- `default_filter`: `name__value`
- `order_by`: `["name__value"]`
- `display_labels`: `["name__value"]`
- `uniqueness_constraints`: `[["name__value"]]`
- `include_in_menu`: `True`
- `icon`: `mdi:key-variant`

### CoreKeyValueStatic (Node, inherits CoreKeyValue)

Plain-text key-value pair for non-sensitive data.

| Field | Type | Kind | Required | Notes |
|-------|------|------|----------|-------|
| `value` | Text | Text | Yes | Stored and displayed as-is |

### CoreKeyValuePassword (Node, inherits CoreKeyValue)

Sensitive key-value pair with masked display.

| Field | Type | Kind | Required | Notes |
|-------|------|------|----------|-------|
| `value` | Password | Password | Yes | Masked as `***` in UI/API; stored as plaintext in DB (same as `shared_key` on webhooks) |

### CoreKeyValueEnvironmentVariable (Node, inherits CoreKeyValue)

Environment-variable-based key-value pair resolved at use time.

| Field | Type | Kind | Required | Notes |
|-------|------|------|----------|-------|
| `value` | Text | Text | Yes | Name of the environment variable (e.g., `MY_AUTH_TOKEN`). Validated against `^[A-Za-z_][A-Za-z0-9_]*$` |

### CoreWebhook (Generic, MODIFIED)

New relationship added to existing generic.

| Relationship | Peer | Kind | Cardinality | Optional | Notes |
|-------------|------|------|-------------|----------|-------|
| `headers` | `CoreKeyValue` | GENERIC | MANY | Yes | Zero or more key-value pairs providing custom HTTP headers |

## Relationships

```
CoreWebhook ──headers──> CoreKeyValue (many-to-many via GENERIC relationship)
     │                        △
     │                       /│\
     ▼                      / │ \
CoreStandardWebhook   Static Password EnvVar
CoreCustomWebhook
```

- One key-value pair can be linked to multiple webhooks (many-to-many)
- One webhook can reference multiple key-value pairs
- Relationship inherited by all webhook node types (`CoreStandardWebhook`, `CoreCustomWebhook`)

## Cache Model

The `Webhook` Pydantic model (used for NATS KV caching) gains a `custom_headers` field:

```python
class HeaderConfig(BaseModel):
    key: str           # HTTP header name
    value: str         # Static/password value or env var name
    header_type: str   # "static" | "password" | "env"

class Webhook(BaseModel):
    # ... existing fields ...
    custom_headers: list[HeaderConfig] = Field(default_factory=list)
```

At send time, headers are resolved:
- `static` / `password`: value used directly
- `env`: `os.environ.get(value)` → actual value or skip + warn

## State Transitions

Key-value pairs are stateless CRUD entities. No state machine applies.

The relevant state change is **cache invalidation**:
1. KV node created/updated/deleted → invalidate caches of all linked webhooks
2. Headers relationship added/removed → invalidate cache of affected webhook

## Validation Rules

| Rule | Scope | Enforcement |
|------|-------|-------------|
| `name` globally unique across all KV types | Generic | `uniqueness_constraints` on generic schema |
| `key` is valid HTTP header name (RFC 7230) | All KV nodes | Attribute `regex` validation |
| `value` on EnvVar matches `^[A-Za-z_][A-Za-z0-9_]*$` | EnvVar node | Attribute `regex` validation |
| Custom header overrides system defaults on name conflict | Send time | Merge logic in `_assign_headers()` |
