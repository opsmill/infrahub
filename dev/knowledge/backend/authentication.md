# Authentication

> Part of: `dev/knowledge/backend/` | Related: [Events System](events.md), [ADR-0005](../../adr/0005-account-group-origin-attribute.md)

Infrahub authenticates users through three flows — password, SSO (OIDC / OAuth2), and native LDAP — that all converge on the same account-resolution and group-resolution pipeline.

## Layout

The `infrahub/auth/` package owns the authentication and group-resolution logic. Native LDAP authentication lives in a sibling package, `infrahub/ldap_auth/`, but plugs into the same downstream pipeline.

```text
infrahub/
  auth/
    auth.py            # Authentication entry points + SSO sign-in flow
    session.py         # AccountSession / AnonymousSession
    types.py           # AuthType enum
    auth_groups/
      service.py       # AutoCreatedGroupsService — find-or-create + membership
      filter.py        # ClaimFilter — regex-driven name extraction
      emitter.py       # AutoCreateEventEmitter (ABC) + Live / Disabled
  ldap_auth/
    service.py         # LDAP bind, group claim extraction
```

`infrahub/auth/__init__.py` re-exports the stable public surface (`signin_sso_account`, `authenticate_with_password`, `AccountSession`, etc.); other modules should import from there rather than from `auth.auth`.

## Entry Points

| Flow | Entry point | Where |
|------|-------------|-------|
| Password | `authenticate_with_password` | `auth/auth.py` |
| SSO (OIDC / OAuth2) | `signin_sso_account` | `auth/auth.py` |
| Native LDAP | `authenticate_with_ldap` (sync wrapper around `LdapAuthService`) | `ldap_auth/service.py` |
| Token validation | `authentication_token`, `validate_jwt_access_token`, `validate_jwt_refresh_token` | `auth/auth.py` |

All flows produce an `AuthResult` and an `AccountSession` that downstream API / GraphQL layers consume.

## SSO Group Resolution Pipeline

On every external login, the resolved account passes through a fixed pipeline that decides which `CoreAccountGroup` rows it ends up a member of:

```text
provider claims  ─►  ClaimFilter  ─►  AutoCreatedGroupsService  ─►  default-group fallback  ─►  membership
                     (regex)         (find-or-create + emit)        (sso_user_default_group)
```

1. **Provider claims** — collected by `get_groups_from_provider` for SSO, or by the LDAP service. The list is raw external identifiers (e.g., `LDAP/group/network-engineering`, `slack/general`).
2. **`ClaimFilter`** — built from the configured `security.auto_create_groups_filter` regex(es). The first pattern that matches a claim wins. A `(?P<name>...)` named capture yields the local group name; otherwise the full claim is used. Patterns without a match are dropped silently.
3. **`AutoCreatedGroupsService.assign`** — for each filtered effective name:
   - Looks up an existing `CoreAccountGroup` by name. Reuse is unbounded.
   - On miss, creates a new `CoreAccountGroup` under a distributed lock (`auto-create-group:<name>` namespace) to serialize concurrent first-logins for the same name. The configured provider name is written to the new row's read-only `origin` attribute.
   - Adds the account as a member of the resolved group, idempotently.
   - Bounds *new creations* by `security.auto_create_groups_max_per_login`. Once the cap is hit, surplus claims that would require a fresh group are dropped — the login still completes.
4. **Default-group fallback** — if no claim matched and `security.sso_user_default_group` is configured, the account is added to that group. Auto-creation and the fallback are mutually exclusive: any successful match suppresses the fallback.

The filter is **opt-in** — when no `auto_create_groups_filter` is configured, `ClaimFilter.is_active` returns `False` and `assign` short-circuits to `()` without touching the database.

## Event Emission

Three events on the `infrahub.group.*` namespace surface the auto-creation activity for audit and automation:

| Event | When |
|-------|------|
| `GroupAutoCreatedEvent` | A new `CoreAccountGroup` was created from a claim |
| `GroupAutoCreateRejectedEvent` | A claim matched the filter but produced an empty / whitespace-only effective name |
| `GroupAutoCreateCappedEvent` | The per-login cap was hit and surplus claims were dropped (at most one per login) |

Emission goes through the `AutoCreateEventEmitter` ABC. Two implementations exist:

- **`LiveAutoCreateEventEmitter`** — sends events through the configured `InfrahubEventService`. Send failures are caught and logged so a broker outage cannot abort a successful login.
- **`DisabledAutoCreateEventEmitter`** — Null Object used when no event service is wired in (e.g., unit tests). Lets `AutoCreatedGroupsService` call the emitter unconditionally without null-checks.

See [Events System](events.md) for the broader event architecture and [`docs/docs/reference/infrahub-events/group.mdx`](../../../docs/docs/reference/infrahub-events/group.mdx) for full event payload shapes.

## Configuration

User-facing keys live under `security.*` in `config.py`:

| Key | Purpose |
|-----|---------|
| `auto_create_groups_filter` | Regex or list of regexes. Empty disables auto-creation. |
| `auto_create_groups_max_per_login` | Per-login cap on new creations. Reuse is uncapped. Default: 50. |
| `sso_user_default_group` | Fallback group when no claim matches. |

The regex(es) are compiled once at config-load time and recompiled when settings are updated.

## Key Locations

| Component | Location |
|-----------|----------|
| Public API surface | `backend/infrahub/auth/__init__.py` |
| SSO sign-in flow | `backend/infrahub/auth/auth.py` (`signin_sso_account`) |
| Filter + matching | `backend/infrahub/auth/auth_groups/filter.py` |
| Find-or-create + membership | `backend/infrahub/auth/auth_groups/service.py` |
| Event emission | `backend/infrahub/auth/auth_groups/emitter.py` |
| Event payloads | `backend/infrahub/events/group_action.py` |
| Config schema | `backend/infrahub/config.py` (`SecuritySettings`) |

## See Also

- [ADR-0005: `origin` attribute for `CoreAccountGroup` provenance](../../adr/0005-account-group-origin-attribute.md)
- [Spec: infp-556 auto-create groups](../../specs/infp-556-auto-create-groups/spec.md)
- [User guide: Auto-create groups from identity provider claims](../../../docs/docs/deploy-manage/user-management/sso/advanced-sso.mdx)
- [Events System](events.md)
