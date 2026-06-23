# Adding an Auth Method

> Part of: `dev/guides/frontend/` | Related: [`dev/knowledge/frontend/auth-methods.md`](../../knowledge/frontend/auth-methods.md)

How to add a new authentication method (LDAP, SAML, magic-link, etc.) to the login page. Read the [auth-methods knowledge doc](../../knowledge/frontend/auth-methods.md) first — it explains the registry pattern this guide plugs into.

The two shapes of new method:

- **Credentials-based** (LDAP, plain username/password against a different endpoint). Reuses `<CredentialsForm>`. Smallest change.
- **Redirect-based** (SSO-like, magic link). Provides its own render component.

The steps below use LDAP as the running example.

## Checklist

- [ ] Add a variant to `AuthMethod` (in `auth-methods.tsx`)
- [ ] Add an api transport + domain function + mutation (only for credentials-style methods that hit a backend)
- [ ] Build a render component (`<LdapCredentialsForm>` or equivalent)
- [ ] Register the method in `AUTH_METHODS`
- [ ] Add tests for the new `resolve` branch and any new render logic
- [ ] Update or add a `LoginErrorCode` if the method needs a distinct error message
- [ ] Run `pnpm biome:fix && pnpm test && pnpm test:e2e -- login`

## 1. Extend the `AuthMethod` union

`frontend/app/src/entities/authentication/auth-methods.tsx`:

```ts
export type AuthMethod =
  | { kind: "local" }
  | { kind: "sso"; providers: Array<SSOProvider> }
  | { kind: "ldap"; displayLabel: string; icon: string }; // NEW
```

The discriminator (`kind`) is the only required field. Add carrier fields only if `render` needs runtime data that `resolve` derived from server config (e.g. SSO's `providers`).

TypeScript will now refuse to compile until `AUTH_METHODS` has an `ldap` entry.

## 2. Add the api transport, domain function, and mutation

Skip this step for purely client-side methods or pure redirects.

The entity follows `ui/ → domain/ → api/` layering. The transport lives in `api/`, the domain function delegates to it, and the mutation wraps the domain function. Never call `apiClient` from `domain/` or `ui/`.

`frontend/app/src/entities/authentication/api/login-with-ldap-from-api.ts`:

```ts
import { apiClient } from "@/shared/api/rest/client";
import type { components } from "@/shared/api/rest/types.generated";

export type LoginWithLdapFromApiParams = { username: string; password: string };

export async function loginWithLdapFromApi(
  params: LoginWithLdapFromApiParams
): Promise<components["schemas"]["UserToken"]> {
  const { data, error, response } = await apiClient.POST("/api/auth/ldap/login", { body: params });

  if (error)
    throw Object.assign(new Error("LDAP login failed"), { status: response.status, body: error });

  return data;
}
```

The throw must carry `status` and `body` — `toLoginError` in `credentials-form.tsx` reads `error.status` to map HTTP codes (401, 403, 409, …) to a `LoginErrorCode`, and falls back to `error.body.message` for the server-provided message. A bare `throw error` drops the status and collapses every failure into the `unknown` branch.

`frontend/app/src/entities/authentication/domain/login-with-ldap.ts`:

```ts
import {
  type LoginWithLdapFromApiParams,
  loginWithLdapFromApi,
} from "@/entities/authentication/api/login-with-ldap-from-api";
import type { UserToken } from "@/entities/authentication/types";

export type LoginWithLdapParams = LoginWithLdapFromApiParams;
export type LoginWithLdap = (params: LoginWithLdapParams) => Promise<UserToken>;

export const loginWithLdap: LoginWithLdap = (params) => loginWithLdapFromApi(params);
```

Rules:

- Domain functions delegate to `api/` — they do not import `apiClient` directly.
- Return the `UserToken`; do **not** call `saveTokensInLocalStorage`. Persistence is centralized in `useAuth.setToken`.

`frontend/app/src/entities/authentication/ui/queries/login-with-ldap.mutation.ts`:

```ts
import { mutationOptions, useMutation } from "@tanstack/react-query";
import { loginWithLdap } from "@/entities/authentication/domain/login-with-ldap";

export function loginWithLdapMutationOptions() {
  return mutationOptions({ mutationKey: ["login-with-ldap"], mutationFn: loginWithLdap });
}

export function useLoginWithLdap() {
  return useMutation(loginWithLdapMutationOptions());
}
```

## 3. Build the render component

For credentials-style methods, wrap `<CredentialsForm>`:

`frontend/app/src/entities/authentication/ui/ldap-credentials-form.tsx`:

```tsx
import { Icon } from "@iconify-icon/react";

import { CredentialsForm } from "@/entities/authentication/ui/credentials-form";
import { useLoginWithLdap } from "@/entities/authentication/ui/queries/login-with-ldap.mutation";

export interface LdapCredentialsFormProps {
  displayLabel: string;
  icon: string;
  className?: string;
}

export const LdapCredentialsForm = ({
  displayLabel,
  icon,
  className,
}: LdapCredentialsFormProps) => {
  const { mutateAsync } = useLoginWithLdap();
  return (
    <CredentialsForm
      onSubmit={mutateAsync}
      className={className}
      submitLabel={
        <>
          <Icon icon={icon} />
          <span className="ml-2">{displayLabel}</span>
        </>
      }
    />
  );
};
```

`displayLabel` and `icon` are threaded through from the server config via the registry entry's `resolve` (see Step 4) so the submit button reflects the deployment's branding.

`<CredentialsForm>` already handles validation, error toasts, and `setToken` — do not re-implement them.

For redirect-style methods, model on `<LoginWithSSOButtons>` (`ui/login-sso-buttons.tsx`).

## 4. Register the method

In `auth-methods.tsx`, add one entry to `AUTH_METHODS`:

```tsx
export const AUTH_METHODS: AuthMethodRegistry = {
  local: { /* unchanged */ },
  sso:   { /* unchanged */ },
  ldap: {
    toggleLabel: ({ displayLabel }) => displayLabel,
    preferDefault: false,
    resolve: (config) =>
      config.ldap?.enabled
        ? { kind: "ldap", displayLabel: config.ldap.display_label, icon: config.ldap.icon }
        : null,
    render: ({ displayLabel, icon }) => (
      <LdapCredentialsForm displayLabel={displayLabel} icon={icon} className="fade-in animate-in" />
    ),
  },
};
```

Decisions to make per entry:

| Field | Question |
|---|---|
| `toggleLabel` | What does the *inactive* toggle button render? A function `(method) => ReactNode` — return a static "Log in with X" string, or thread per-deployment data (display label, icon) from the variant. |
| `preferDefault` | Should this be the initial selection when no preference is stored? At most one method should be `true` for the typical install. |
| `resolve` | Read whatever server config flags this method. Return `null` to filter it out entirely (e.g. backend feature disabled, no providers configured). |
| `render` | The component that owns the per-method UI. Pass `fade-in animate-in` to match the existing transitions. |

That's the whole UI change. `LoginMethodPicker` automatically:

- Includes the method in toggles when `resolve` returns non-null.
- Persists the user's choice via `useLastUsedMethod`.
- Restores it on next visit.

## 5. Adjust error mapping (only if needed)

If the new method needs a distinct error message (e.g. "LDAP server unreachable"), update both:

1. `types.ts` — add the code to `LoginErrorCode`.
2. `constants.ts` — add the entry to `LOGIN_ERRORS`.
3. `credentials-form.tsx` — extend `toLoginError(error)` with the new branch.

Resist adding bespoke error mappers per-method. The shared classifier is what keeps the UX consistent across forms.

## 6. Tests to add

- **`use-available-auth-methods.test.ts`** — one test per `resolve` outcome of the new method (enabled, disabled, edge cases).
- **`<XxxCredentialsForm>.test.tsx`** — only if the wrapper has logic beyond passing `mutateAsync` to `<CredentialsForm>`. Otherwise the `CredentialsForm` suite already covers the behavior.
- **`login-method-picker.test.tsx`** — add a test for the 3-method picker if the toggle ordering or default-selection logic needs to change.
- **`tests/e2e/login.spec.ts`** — add a happy-path spec using the new toggle label.

## 7. Verify

```bash
cd frontend/app && pnpm biome:fix
cd frontend/app && pnpm test
cd frontend/app && pnpm test:e2e -- login
```

Run a manual smoke test of the picker in `pnpm dev`: confirm (a) the toggle shows when the method is enabled, (b) it hides when disabled, (c) the last-used selection persists across reloads.

## Anti-patterns

| Don't | Do |
|---|---|
| Branch on `method.kind` inside `LoginMethodPicker`. | Add the new behavior to the registry entry's `render` or `resolve`. |
| Call `saveTokensInLocalStorage` from the new domain function. | Return the token; `useAuth.setToken` writes it. |
| Copy-paste `<CredentialsForm>` to customize one piece. | Add a prop (e.g. `errorMapper`) to `<CredentialsForm>` if the override is genuinely shared; otherwise wrap and compose. |
| Write a one-off `useState` toggle in the picker for the new method. | Trust `useLastUsedMethod` — it already handles N methods. |
| Add a method-specific localStorage key. | Reuse `LAST_USED_METHOD_KEY`. The `kind` discriminator is the persisted value. |

## Related

- Pattern reference: [`dev/knowledge/frontend/auth-methods.md`](../../knowledge/frontend/auth-methods.md)
- Entities structure: [`dev/knowledge/frontend/entities-structure.md`](../../knowledge/frontend/entities-structure.md)
- Naming: [`dev/guidelines/frontend/naming-conventions.md`](../../guidelines/frontend/naming-conventions.md)
- Component reuse: [`dev/guidelines/frontend/component-patterns.md`](../../guidelines/frontend/component-patterns.md)
