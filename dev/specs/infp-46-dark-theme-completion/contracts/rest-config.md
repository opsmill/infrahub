# Contract: deployment default theme on the config payload

**Feature**: [spec.md](../spec.md) | **Covers**: FR-010, FR-011, FR-012

The deployment default is not a preference — it is a property of the running deployment, needed
before a user exists. It therefore travels on the unauthenticated config payload, not over GraphQL.

⚠ `schema/openapi.json` and `frontend/app/src/shared/api/rest/types.generated.ts` are generated.
Regenerate with `uv run invoke schema.generate-jsonschema` and `cd frontend/app && pnpm codegen`, and
commit; CI validates them.

## Why this endpoint

`backend/infrahub/api/internal.py` exposes two endpoints with different auth postures:

| Endpoint | Auth | Carries |
|---|---|---|
| `GET /api/config` | **none** | `main`, `logging`, `analytics`, `experimental_features`, `sso`, `ldap`, `installation_type`, `policy` |
| `GET /api/info` | `Depends(get_current_user)` | `deployment_id`, `version` |

The login page must paint a theme before there is a session, so the value must come from the
unauthenticated endpoint. The version lives only on the authenticated one.

⚠ **The frontend must not derive this itself.** It cannot read the version pre-login, and duplicating
PEP 440 parsing in TypeScript would drift from the backend's answer. The backend publishes the
resolved result.

⚠ **Only the resolved value is published, never the version.** `light` or `dark` tells an anonymous
caller nothing about the build; putting the version string on an unauthenticated endpoint would newly
expose it and is not required.

## Payload delta

```diff
 class ConfigAPI(BaseModel):
     main: MainSettings
     logging: LoggingSettings
     analytics: AnalyticsSettings
     experimental_features: ExperimentalFeaturesSettings
     sso: config.SSOInfo
     ldap: config.LDAPInfo
     installation_type: str
     policy: config.PolicySettings
+    default_theme: Literal["light", "dark"]
```

Always concrete — never `system`. A server cannot observe an operating system's appearance, and a
`system` default would leave the client with nothing to fall back to before its mirror exists.

## Resolution

```text
default_theme
  = operator override, when explicitly configured
  | "dark"   when Version(infrahub.__version__).is_prerelease
  | "light"  otherwise
```

Verified shapes (see [research.md](../research.md) §R1):

| Version | `is_prerelease` | `default_theme` |
|---|---|---|
| `1.11.0b2.dev134+geb5acb009` | `True` | `dark` |
| `1.12.0.dev5+g1a2b3c` | `True` | `dark` |
| `1.11.1rc1` | `True` | `dark` |
| `1.11.0` | `False` | `light` |

⚠ `installation_type` is **not** the signal. It is `"community"` — community versus enterprise, not
production versus non-production. Its presence on this same payload makes it an easy false lead.

## Operator override

A new setting under the existing `INFRAHUB_EXPERIMENTAL_` family, tri-state so that "not configured"
stays distinguishable from "explicitly light":

```python
class ExperimentalFeaturesSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_EXPERIMENTAL_")
    graphql_enums: bool = False
    value_db_index: bool = Field(default=False, deprecated="…")
    default_theme: Literal["light", "dark"] | None = None   # None → derive from version
```

⚠ A plain `bool` would be wrong: `False` could not be told apart from unset, so an operator could
never force light on a pre-release build, and FR-012 would be unmet in one direction.

## Behavioural contract

| Given | When | Then |
|---|---|---|
| Pre-release build, no override | `GET /api/config` | `default_theme = "dark"` |
| Release build, no override | `GET /api/config` | `default_theme = "light"` |
| Pre-release build, override `light` | `GET /api/config` | `default_theme = "light"` |
| Release build, override `dark` | `GET /api/config` | `default_theme = "dark"` |
| Any build | anonymous request | succeeds; no version information disclosed |
| User has a stored preference | any deployment default | the stored preference wins; the default is never written to storage (FR-013) |
| Deployment upgrades pre-release → release | users who chose a theme | unaffected — only un-chosen users' effective theme changes |

## Consumer contract

The client treats `default_theme` as the substitute for a `DEFAULT`-sourced effective preference:

```text
choice   = effective.theme.value ?? config.default_theme
resolved = choice == SYSTEM ? (prefers-color-scheme: dark ? dark : light) : choice
```

`resolved` is then mirrored to `localStorage` so the next load's inline script paints correctly from
the first frame.
