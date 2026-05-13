# IFC-2595 — Frontend login refactor (prepare for LDAP)

**Status:** Draft
**Branch:** `ple-login-ifc-2595`
**Date:** 2026-05-13
**Scope:** Frontend only (`frontend/app/src/entities/authentication/` + `pages/login.tsx`)

## Problem

Today Infrahub's frontend supports two authentication paths: a local username/password form (`POST /api/auth/login`) and SSO (OAuth2/OIDC redirect flows). A third method — native LDAP — is on the roadmap (referenced in INFP-105 / INFP-556). LDAP, from the UI's perspective, is a credentials form (username + password) pointed at a different endpoint.

The current code is *structurally* set up to make adding LDAP painful:

- The login UI uses a binary `useState(displaySSO)` toggle. A third method requires re-shaping the picker.
- The credentials form, its react-query mutation, and its domain function are all hardwired to `/api/auth/login`. The form cannot be reused for LDAP without copy-paste.
- Token persistence (`saveTokensInLocalStorage`) runs both inside the login domain function and again inside `setToken` in `useAuth`. The access token is written to localStorage twice per login. Not a runtime bug, but a leaky boundary that makes "what owns persistence?" unclear when a third method is added.
- Error handling is inconsistent: the local form shows a fixed generic toast; the SSO callback pushes shaped error objects through `location.state`; refresh failure does `window.location.reload()`. There is no shared `LoginError` type.
- There is no `AuthMethod` concept. Adding a method requires editing several files in lockstep.
- Component names mislead: `Login` is a *method picker*; `LoginForm` is the *local-credentials form*. With LDAP both names will be wrong.
- No unit tests for the auth module — only Playwright e2e coverage.

## Goal

Refactor the existing auth UI so that **adding LDAP later is a small, mechanical change** — ideally one new domain file, one new mutation file, one new wrapper component, and one line in a method registry. Along the way, fix the token-duplication smell and standardize error display.

**This spec ships no LDAP code.** It ships the scaffolding only.

## Non-Goals

- Do not modify the refresh-token flow (`refresh-access-token.ts`, `useLocalStorage` interaction).
- Do not modify the SSO callback page (`pages/auth-callback.tsx`) beyond what is required to use the new `LoginError` type.
- Do not modify `RequireAuth`.
- Do not modify the logout flow.
- Do not modify the backend.

## Affected files

```
frontend/app/src/entities/authentication/
  types.ts                                  MODIFY  add AuthMethod, LoginError
  constants.ts                              MODIFY  add LAST_USED_METHOD_KEY
  utils.ts                                  unchanged
  domain/
    login-with-credentials.ts               MODIFY  stop calling saveTokensInLocalStorage
    refresh-access-token.ts                 unchanged
    logout.ts                               unchanged
  ui/
    login.tsx                               DELETE  replaced by login-method-picker
    login-method-picker.tsx                 NEW
    credentials-form.tsx                    NEW     generic form, takes onSubmit prop
    local-credentials-form.tsx              NEW     wires CredentialsForm to local mutation
    login-sso-buttons.tsx                   unchanged
    use-available-auth-methods.ts           NEW     derives AuthMethod[] from config
    useAuth.tsx                             unchanged
    require-auth.tsx                        unchanged
    queries/
      login-with-credentials.mutation.ts    unchanged
frontend/app/src/pages/
  login.tsx                                 MODIFY  import LoginMethodPicker
  auth-callback.tsx                         unchanged (uses existing setToken path)
```

Tests added:

```
frontend/app/src/entities/authentication/ui/
  credentials-form.test.tsx                 NEW
  login-method-picker.test.tsx              NEW
  use-available-auth-methods.test.ts        NEW
```

## Design

### 1. `AuthMethod` type (`types.ts`)

```typescript
import type { components } from "@/shared/api/rest/types.generated";
import type { SSOProvider } from "@/entities/config/types";

export type User = { id: string };
export type UserToken = components["schemas"]["UserToken"];

export type LoginError = {
  code: "invalid_credentials" | "network" | "server" | "unknown";
  message: string;
};

export type AuthMethod =
  | { kind: "local"; label: string }
  | { kind: "sso"; providers: SSOProvider[] };
// LDAP follow-up will add: | { kind: "ldap"; label: string };
```

The union is the **single source of truth** for what methods exist. `useAvailableAuthMethods` is responsible for deriving the list from server config.

### 2. `useAvailableAuthMethods` hook (`ui/use-available-auth-methods.ts`)

```typescript
export function useAvailableAuthMethods(): AuthMethod[] {
  const config = useConfig();
  const methods: AuthMethod[] = [{ kind: "local", label: "Username & password" }];
  if (config?.sso.enabled && config.sso.providers?.length) {
    methods.push({ kind: "sso", providers: config.sso.providers });
  }
  return methods;
}
```

Rationale: derive client state from server config in one place. Tests assert: (a) local-only when SSO disabled, (b) local + SSO when SSO has providers, (c) local-only when SSO enabled but `providers` is empty.

### 3. `<CredentialsForm>` (`ui/credentials-form.tsx`)

Pure presentation. No knowledge of which endpoint it calls.

```typescript
export interface CredentialsFormProps {
  onSubmit: (values: { username: string; password: string }) => Promise<UserToken>;
  submitLabel?: string;            // default: "Log in"
  className?: string;
}
```

Responsibilities:
- Render `InputField` for username + `PasswordInputField` for password (existing components).
- Validate `required` on both fields (existing `isRequired` validator).
- On submit, call `props.onSubmit(values)`, then call `setToken(result)` (from `useAuth()`) on success.
- On failure, map the error to a `LoginError` and surface a toast via `<Alert>`.
- Autofocus username field (preserves current behavior).

Error mapping (in this component, single place):
```typescript
function toLoginError(error: unknown): LoginError {
  if (error?.status === 401) return { code: "invalid_credentials", message: "Invalid username or password" };
  if (error?.status >= 500)  return { code: "server",              message: "Authentication service unavailable" };
  if (!navigator.onLine)     return { code: "network",             message: "Network error — check your connection" };
  return { code: "unknown",  message: "Could not log in" };
}
```

This is where future LDAP-specific errors (e.g. "LDAP server unreachable") will be added by passing an optional `errorMapper` prop. We do **not** add `errorMapper` now (YAGNI); the LDAP work introduces it.

### 4. `<LocalCredentialsForm>` (`ui/local-credentials-form.tsx`)

Thin wrapper — the only place that wires the local mutation:

```typescript
export const LocalCredentialsForm = ({ className }: { className?: string }) => {
  const { mutateAsync } = useLoginWithCredentials();
  return <CredentialsForm onSubmit={mutateAsync} className={className} />;
};
```

When LDAP lands, a sibling `<LdapCredentialsForm>` is added with the same shape, wiring `useLoginWithLdap()`.

### 5. `<LoginMethodPicker>` (`ui/login-method-picker.tsx`)

Replaces the existing `Login` component. Behavior:

- **0 methods**: render an error message. (Defensive — shouldn't happen because `local` is always present.)
- **1 method**: render that method's form/buttons directly, no picker chrome.
- **2+ methods**: render the active method's content plus toggle buttons for the others. Initial selection comes from `localStorage[LAST_USED_METHOD_KEY]` if set and still available; otherwise the first method.

```typescript
export const LoginMethodPicker = () => {
  const methods = useAvailableAuthMethods();
  const [active, setActive] = useLastUsedMethod(methods);
  // …renders active method + "Log in with X" buttons for the others
};
```

The toggle button text is derived from the inactive method's kind:
- `local` → "Log in with your credentials"
- `sso`   → "Log in with SSO"
- (later) `ldap` → "Log in with LDAP"

This is the only place that needs to know the human label for switching between methods. Adding LDAP = adding one case in the label switch + one render case.

### 6. Token persistence rule

Remove the `saveTokensInLocalStorage(data)` call from `domain/login-with-credentials.ts`. The contract becomes:

> Domain functions return tokens. The **AuthContext** (`useAuth.setToken`) is the only writer to localStorage during interactive login flows.

The exception is `domain/refresh-access-token.ts`, which runs outside React (called from an API interceptor) and must persist directly. Its behavior is unchanged.

### 7. Page glue (`pages/login.tsx`)

Replace `<Login />` with `<LoginMethodPicker />`. No other changes.

## Data flow

```
useConfig() ─► useAvailableAuthMethods() ─► AuthMethod[]
                                              │
                                              ▼
                                     <LoginMethodPicker>
                            ┌────────────────┼────────────────┐
                            ▼                ▼                ▼
                  <LocalCredentialsForm> <LdapCredsForm>* <LoginSSOButtons>
                            │                │                │
                            └─► useLogin...().mutateAsync  ◄──┘
                                              │
                                              ▼
                                  setToken(result) (AuthContext)
                                              │
                                              ▼
                                  localStorage (single write site)
```
`*` = added by the LDAP follow-up.

## Edge cases

| Scenario | Behavior |
|---|---|
| SSO disabled, no LDAP | Picker renders local form only, no toggle. |
| SSO enabled, 0 providers | `useAvailableAuthMethods` filters SSO out. Local-only picker. |
| SSO enabled, 1+ providers | 2-method picker. Last-used method remembered. |
| LDAP enabled (future) | 3-method picker. Toggle cycles through all available. |
| `localStorage[LAST_USED_METHOD_KEY]` references a method no longer available | Fall back to the first method. |
| Form submit while network is offline | Toast: "Network error — check your connection". |
| 401 from auth endpoint | Toast: "Invalid username or password". |
| 5xx from auth endpoint | Toast: "Authentication service unavailable". |
| SSO callback error | Existing `location.state.errors` path unchanged. |

## Testing

**Unit (Vitest + React Testing Library):**

- `use-available-auth-methods.test.ts`
  - returns `[local]` when SSO disabled
  - returns `[local, sso]` when SSO enabled with providers
  - returns `[local]` when SSO enabled with empty providers list
- `credentials-form.test.tsx`
  - renders username + password fields with required validation
  - calls `onSubmit` with form values
  - calls `setToken` on success
  - shows "Invalid username or password" on 401
  - shows "Authentication service unavailable" on 500
- `login-method-picker.test.tsx`
  - renders the lone method directly when only one is available (no toggle button)
  - renders toggle when 2+ methods available
  - restores last-used method from localStorage
  - falls back gracefully when stored method is no longer available

**E2E (Playwright — already exists):**

`tests/e2e/login.spec.ts` is preserved as-is. Selectors used (`getByRole("button", { name: "Log in" })`, `getByRole("button", { name: "Log in with SSO" })`, `getByRole("button", { name: "Log in with your credentials" })`) continue to match. No e2e changes required for this refactor.

## Acceptance criteria

1. All existing Playwright `login.spec.ts` tests pass without modification.
2. `pnpm biome:fix` and `pnpm test` pass.
3. `saveTokensInLocalStorage` is called from exactly two places: `useAuth.setToken` and `domain/refresh-access-token.ts`.
4. Adding LDAP to the codebase requires only: (a) one new domain file, (b) one new mutation file, (c) one new `<LdapCredentialsForm>` wrapper, (d) one new branch in `AuthMethod`, (e) one push in `useAvailableAuthMethods`, (f) one label case in `LoginMethodPicker`. No other file edits.
5. Token writes during interactive login happen once per token, not twice.
6. Error messages distinguish invalid credentials, network, server, and unknown failures.

## Risks

- **Test selector regressions.** The picker's toggle button labels must match the existing e2e expectations exactly. Mitigation: verify selectors before merging.
- **`useLastUsedMethod` localStorage stale value.** Already addressed in the edge-case table: fall back to first method.
- **Scope creep into auth-callback.** Explicitly out of scope; reviewers should push back if the diff grows there.

## Follow-up (separate work)

- LDAP integration (INFP-105): adds `<LdapCredentialsForm>` and the LDAP branch.
- Refresh-token UX (no spec yet): remove the `window.location.reload()` jolt.
- Auth-callback generalization (no spec yet): only if a non-OAuth/OIDC redirect-style method is ever needed.
