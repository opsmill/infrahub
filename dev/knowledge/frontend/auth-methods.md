# Auth Methods

Location: `frontend/app/src/entities/authentication/`

How the login UI supports multiple authentication methods (local credentials, SSO, LDAP) through a single registry.

## Folder layout

Each method's files are colocated in `methods/<kind>/`. Shared infrastructure (registry, `CredentialsForm`, picker, hooks, `useAuth`) lives at the entity root or under `ui/`.

```text
authentication/
├── auth-methods.tsx              # registry: AUTH_METHODS, AuthMethod union, helpers
├── constants.ts / types.ts / utils.ts
├── methods/
│   ├── local/                    # one folder per method
│   │   ├── local-credentials-form.tsx
│   │   ├── login-with-credentials.ts             # domain
│   │   └── login-with-credentials.mutation.ts    # query
│   ├── sso/
│   │   └── login-sso-buttons.tsx
│   └── ldap/
│       ├── ldap-credentials-form.tsx
│       ├── login-with-ldap.ts
│       └── login-with-ldap.mutation.ts
├── domain/                       # cross-method (logout, refresh)
└── ui/                           # cross-method (picker, CredentialsForm, useAuth, hooks)
```

## The registry

A single `AUTH_METHODS` object in `auth-methods.tsx` is the source of truth for every method the UI knows about. Each entry is keyed by an `AuthMethod["kind"]` discriminator and provides four fields:

```ts
type AuthMethodDefinition<TMethod extends AuthMethod> = {
  toggleLabel: (method: TMethod) => ReactNode; // shown in the picker switch button
  preferDefault: boolean;                    // initial selection when nothing is stored
  resolve: (config: ConfigAPI) => TMethod | null; // null = unavailable for this server
  render: (method: TMethod) => ReactNode;    // the UI for this method
};
```

`AuthMethod` is a discriminated union (`{ kind: "local" } | { kind: "sso"; providers: [...] } | ...`). The registry type `AuthMethodRegistry` is keyed on `kind`, so TypeScript enforces that every variant has a definition.

```ts
export const AUTH_METHODS: AuthMethodRegistry = {
  local: { toggleLabel: () => "Log in with your credentials", preferDefault: false, resolve: () => ({ kind: "local" }), render: () => <LocalCredentialsForm /> },
  sso:   { toggleLabel: () => "Log in with SSO",              preferDefault: true,  resolve: (c) => c.sso?.enabled && c.sso.providers?.length ? { kind: "sso", providers: c.sso.providers } : null, render: ({ providers }) => <LoginWithSSOButtons providers={providers} /> },
  ldap:  { toggleLabel: ({ displayLabel }) => displayLabel,   preferDefault: false, resolve: (c) => c.ldap?.enabled ? { kind: "ldap", displayLabel: c.ldap.display_label, icon: c.ldap.icon } : null, render: ({ displayLabel, icon }) => <LdapCredentialsForm displayLabel={displayLabel} icon={icon} /> },
};
```

Adding a new method = adding one variant to `AuthMethod` and one entry to `AUTH_METHODS`. The picker, last-used persistence, and toggle labels pick it up automatically.

## Data flow

```text
useConfig() ─► resolveAvailableAuthMethods(config) ─► AuthMethod[]
                       ▲                                  │
                       │                                  ▼
                       │                         <LoginMethodPicker>
                       │                  ┌───────────────┼───────────────┐
                       │                  ▼               ▼               ▼
              AUTH_METHODS[k].resolve   render(active)  toggle buttons (others)
                                         │
                                         ▼
                              <LocalCredentialsForm> / <LoginWithSSOButtons> / ...
                                         │
                                         ▼
                            mutateAsync ─► setToken(result)  (useAuth)
                                                │
                                                ▼
                                    localStorage (interactive write site;
                                     background refresh writes directly —
                                     see refresh-access-token)
```

## Components and hooks

| File | Responsibility |
|---|---|
| `auth-methods.tsx` | `AuthMethod` union, `AUTH_METHODS` registry, `resolveAvailableAuthMethods`, `renderAuthMethod`. |
| `types.ts` | `UserToken`, `LoginError`, `LoginErrorCode`. |
| `constants.ts` | `ACCESS_TOKEN_KEY`, `REFRESH_TOKEN_KEY`, `LAST_USED_METHOD_KEY`, `LOGIN_ERRORS` map. |
| `ui/use-available-auth-methods.ts` | Hook wrapping `resolveAvailableAuthMethods(useConfig())`. |
| `ui/use-last-used-method.ts` | Persists active method in `localStorage[LAST_USED_METHOD_KEY]`, falls back when stored kind is no longer available. |
| `ui/login-method-picker.tsx` | Renders active method via `renderAuthMethod`, plus toggle buttons for the others. |
| `ui/credentials-form.tsx` | Endpoint-agnostic username/password form. Takes `onSubmit: (values) => Promise<UserToken>`. Maps thrown errors to `LoginError` and toasts. Calls `useAuth().setToken` on success. |
| `methods/local/local-credentials-form.tsx` | Wires `CredentialsForm` to `useLoginWithCredentials()`. |
| `methods/sso/login-sso-buttons.tsx` | Renders one redirect link per SSO provider. |
| `methods/ldap/ldap-credentials-form.tsx` | Wires `CredentialsForm` to `useLoginWithLdap()`, with the configured `display_label` + `icon` as the submit button. |
| `ui/useAuth.tsx` | `AuthContext`. `setToken` is the **only** writer of access/refresh tokens to localStorage during interactive login. |
| `methods/local/login-with-credentials.ts` | Domain function. Returns `UserToken`; does **not** persist. |
| `methods/ldap/login-with-ldap.ts` | Domain function for LDAP. Returns `UserToken`. |
| `domain/refresh-access-token.ts` | Background refresh from API interceptor. Writes localStorage directly (runs outside React). |
| `methods/local/login-with-credentials.mutation.ts` | TanStack mutation wrapping the local domain function. |
| `methods/ldap/login-with-ldap.mutation.ts` | TanStack mutation wrapping the LDAP domain function. |

## Contracts that make adding a method mechanical

1. **Registry-driven UI.** `LoginMethodPicker` calls `useAvailableAuthMethods()` and `renderAuthMethod(active)`. It never branches on `kind`. Toggle labels come from `AUTH_METHODS[kind].toggleLabel`.
2. **`resolve` is the only place that reads server config.** Returning `null` filters the method out of the picker. Empty-but-enabled cases (SSO enabled with zero providers) are handled inside `resolve`.
3. **`preferDefault` chooses the initial active method** when nothing is stored. Exactly one method should set it to `true` for the typical install (today: SSO). A stored `LAST_USED_METHOD_KEY` always overrides this.
4. **`CredentialsForm` is reusable.** Any credentials-based method (local today, LDAP tomorrow) wires its own mutation through the `onSubmit` prop. The form owns validation, error mapping, and `setToken` on success.
5. **Token persistence is centralized.** Domain functions return tokens; `useAuth.setToken` is the single writer for interactive flows. Only `refresh-access-token` may write directly, because it runs outside React.
6. **Errors are typed and centralized.** `LOGIN_ERRORS` in `constants.ts` is the map; `toLoginError(error)` in `credentials-form.tsx` is the only classifier. Add a new `LoginErrorCode` there if a new method needs a distinct message.

## Default-method behavior

When 2+ methods are available and no preference is stored, `LoginMethodPicker` picks the first method whose `preferDefault` is `true` (today: SSO). This preserves the pre-refactor UX. Tests cover both branches (stored value wins, default applies otherwise).

## Persistence keys

| Key | Owner | Lifetime |
|---|---|---|
| `access_token` | `useAuth.setToken` (interactive) + `refresh-access-token` (background) | Until logout. |
| `refresh_token` | Same as above. | Until logout. |
| `auth_last_used_method` | `useLastUsedMethod`. | Until cleared; survives logout intentionally so returning users land on the same picker tab. |

## Tests

| File | Covers |
|---|---|
| `ui/use-available-auth-methods.test.ts` | Each `resolve` branch: SSO disabled, SSO with providers, SSO enabled but empty providers. |
| `ui/use-last-used-method.test.ts` | First-method default, stored-value restore, stale-value fallback, `setActive` write-through, empty methods. |
| `ui/credentials-form.test.tsx` | Field rendering, `onSubmit` call shape, success → `setToken`, error → toast (401, 5xx, network, unknown), required-validation. |
| `ui/login-method-picker.test.tsx` | Solo method (no toggle), 2-method picker, default-to-SSO, restore from storage, stale-storage fallback. |

E2E coverage lives in `frontend/app/tests/e2e/login.spec.ts`. Selectors target `Log in`, `Log in with SSO`, and `Log in with your credentials` — these strings are part of the contract.
