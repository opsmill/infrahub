# IFC-2595 — Frontend login refactor: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the frontend authentication UI so that adding a third login method (LDAP) becomes a small, mechanical change — without altering the refresh-token, logout, SSO-callback, or `RequireAuth` flows.

**Architecture:** Introduce an `AuthMethod` discriminated union as the registry of available methods, a `useAvailableAuthMethods` hook that derives the list from server config, a generic `<CredentialsForm>` parameterized by an `onSubmit` callback, thin wrapper components per method (`<LocalCredentialsForm>`, later `<LdapCredentialsForm>`), a `<LoginMethodPicker>` that handles 1/2/3+ methods with last-used-method memory, and a single token-persistence site (`useAuth.setToken`).

**Tech Stack:** React 19, TypeScript 5.9, react-router, @tanstack/react-query, react-toastify, vitest-browser-react, Vitest, Tailwind, openapi-fetch (already wired via `@/shared/api/rest/client`), `react-hook-form` via the project's `Form` wrapper.

**Spec:** `dev/specs/ifc-2595-login-refactor/spec.md`

---

## File map

Each row maps to one or more tasks below.

| File | Action | Task |
|---|---|---|
| `frontend/app/src/entities/authentication/types.ts` | MODIFY (add `LoginError`, `AuthMethod`) | 1 |
| `frontend/app/src/entities/authentication/constants.ts` | MODIFY (add `LAST_USED_METHOD_KEY`) | 1 |
| `frontend/app/src/entities/authentication/ui/use-available-auth-methods.ts` | NEW | 2 |
| `frontend/app/src/entities/authentication/ui/use-available-auth-methods.test.ts` | NEW | 2 |
| `frontend/app/src/entities/authentication/ui/credentials-form.tsx` | NEW | 3 |
| `frontend/app/src/entities/authentication/ui/credentials-form.test.tsx` | NEW | 3 |
| `frontend/app/src/entities/authentication/ui/local-credentials-form.tsx` | NEW | 4 |
| `frontend/app/src/entities/authentication/ui/use-last-used-method.ts` | NEW | 5 |
| `frontend/app/src/entities/authentication/ui/use-last-used-method.test.ts` | NEW | 5 |
| `frontend/app/src/entities/authentication/ui/login-method-picker.tsx` | NEW | 6 |
| `frontend/app/src/entities/authentication/ui/login-method-picker.test.tsx` | NEW | 6 |
| `frontend/app/src/pages/login.tsx` | MODIFY (swap component) | 7 |
| `frontend/app/src/entities/authentication/ui/login.tsx` | DELETE | 7 |
| `frontend/app/src/entities/authentication/domain/login-with-credentials.ts` | MODIFY (drop `saveTokensInLocalStorage` call) | 8 |
| `frontend/app/src/entities/authentication/ui/login-sso-buttons.tsx` | unchanged | — |
| `frontend/app/src/entities/authentication/ui/useAuth.tsx` | unchanged | — |
| `frontend/app/src/entities/authentication/ui/require-auth.tsx` | unchanged | — |
| `frontend/app/src/entities/authentication/domain/refresh-access-token.ts` | unchanged | — |
| `frontend/app/src/entities/authentication/domain/logout.ts` | unchanged | — |
| `frontend/app/src/pages/auth-callback.tsx` | unchanged | — |
| `frontend/app/tests/e2e/login.spec.ts` | unchanged (must keep passing) | 9 |

---

## Conventions referenced

- Test wrapper: `frontend/app/tests/components/render.tsx` exposes `render()` which sets up `BrowserRouter`, `QueryClientProvider`, jotai `Provider`, `ToastContainer`, and a default `BranchContext`. Wrap config-dependent components in `<ConfigContext value={config}>` from `@/entities/config/ui/config-provider`.
- Mocking: use `vi.mock("...")` then `vi.mocked(fn).mockReturnValue(...)` (see `entities/config/ui/about-modal.test.tsx`).
- File naming: tests live next to the file under test, suffix `.test.ts` or `.test.tsx`.
- Form fields: `InputField` and `PasswordInputField` from `@/shared/components/form/fields/*`, validator `isRequired` from `@/shared/components/form/utils/validation`.
- Toasts: `toast(<Alert type={ALERT_TYPES.ERROR} message="..." />, { toastId: "..." })` from `react-toastify` + `@/shared/components/ui/alert`.
- All commits use `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` per repo norms.

---

## Task 1 — Add `AuthMethod`, `LoginError`, and `LAST_USED_METHOD_KEY`

**Files:**
- Modify: `frontend/app/src/entities/authentication/types.ts`
- Modify: `frontend/app/src/entities/authentication/constants.ts`

No unit tests — pure type and constant declarations.

- [ ] **Step 1: Add `LoginError` and `AuthMethod` to `types.ts`**

Replace the contents of `frontend/app/src/entities/authentication/types.ts` with:

```typescript
import type { components } from "@/shared/api/rest/types.generated";

import type { SSOProvider } from "@/entities/config/types";

export type User = {
  id: string;
};

export type UserToken = components["schemas"]["UserToken"];

export type LoginError = {
  code: "invalid_credentials" | "network" | "server" | "unknown";
  message: string;
};

export type AuthMethod =
  | { kind: "local"; label: string }
  | { kind: "sso"; providers: Array<SSOProvider> };
// Future: | { kind: "ldap"; label: string };

export type AuthMethodKind = AuthMethod["kind"];
```

- [ ] **Step 2: Add `LAST_USED_METHOD_KEY` to `constants.ts`**

Replace the contents of `frontend/app/src/entities/authentication/constants.ts` with:

```typescript
export const ACCESS_TOKEN_KEY = "access_token";
export const REFRESH_TOKEN_KEY = "refresh_token";
export const LAST_USED_METHOD_KEY = "auth_last_used_method";
```

- [ ] **Step 3: Type-check passes**

Run from `frontend/app`:

```bash
pnpm exec tsc --noEmit -p tsconfig.app.json
```

Expected: exits 0 with no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/src/entities/authentication/types.ts \
        frontend/app/src/entities/authentication/constants.ts
git commit -m "$(cat <<'EOF'
refactor(auth): introduce AuthMethod and LoginError types

Adds the AuthMethod discriminated union and LoginError shape used by the
upcoming LoginMethodPicker and CredentialsForm. No behavior change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — `useAvailableAuthMethods` hook

**Files:**
- Create: `frontend/app/src/entities/authentication/ui/use-available-auth-methods.ts`
- Create: `frontend/app/src/entities/authentication/ui/use-available-auth-methods.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/app/src/entities/authentication/ui/use-available-auth-methods.test.ts`:

```typescript
import { renderHook } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { useConfig } from "@/entities/config/ui/config-provider";

import { useAvailableAuthMethods } from "./use-available-auth-methods";

vi.mock("@/entities/config/ui/config-provider");

describe("useAvailableAuthMethods", () => {
  test("returns [local] when SSO is disabled", () => {
    vi.mocked(useConfig).mockReturnValue({
      sso: { enabled: false, providers: [] },
    } as any);

    const { result } = renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([{ kind: "local", label: "Username & password" }]);
  });

  test("returns [local, sso] when SSO is enabled with at least one provider", () => {
    const providers = [
      {
        name: "google",
        display_label: "Google",
        icon: "mdi:google",
        protocol: "oauth2",
        authorize_path: "/api/oauth2/google/authorize",
        token_path: "/api/oauth2/google/token",
      },
    ];
    vi.mocked(useConfig).mockReturnValue({
      sso: { enabled: true, providers },
    } as any);

    const { result } = renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([
      { kind: "local", label: "Username & password" },
      { kind: "sso", providers },
    ]);
  });

  test("returns [local] when SSO is enabled but providers list is empty", () => {
    vi.mocked(useConfig).mockReturnValue({
      sso: { enabled: true, providers: [] },
    } as any);

    const { result } = renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([{ kind: "local", label: "Username & password" }]);
  });

  test("returns [local] when SSO is enabled but providers is undefined", () => {
    vi.mocked(useConfig).mockReturnValue({
      sso: { enabled: true },
    } as any);

    const { result } = renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([{ kind: "local", label: "Username & password" }]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend/app && pnpm test src/entities/authentication/ui/use-available-auth-methods.test.ts
```

Expected: FAIL — module `./use-available-auth-methods` does not exist.

- [ ] **Step 3: Implement the hook**

Create `frontend/app/src/entities/authentication/ui/use-available-auth-methods.ts`:

```typescript
import { useConfig } from "@/entities/config/ui/config-provider";

import type { AuthMethod } from "@/entities/authentication/types";

export function useAvailableAuthMethods(): Array<AuthMethod> {
  const config = useConfig();

  const methods: Array<AuthMethod> = [{ kind: "local", label: "Username & password" }];

  if (config?.sso?.enabled && config.sso.providers && config.sso.providers.length > 0) {
    methods.push({ kind: "sso", providers: config.sso.providers });
  }

  return methods;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend/app && pnpm test src/entities/authentication/ui/use-available-auth-methods.test.ts
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/src/entities/authentication/ui/use-available-auth-methods.ts \
        frontend/app/src/entities/authentication/ui/use-available-auth-methods.test.ts
git commit -m "$(cat <<'EOF'
feat(auth): add useAvailableAuthMethods hook

Derives the list of available auth methods (local, sso) from server
config. Single source of truth for "which methods are available", used
by the upcoming LoginMethodPicker.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — `<CredentialsForm>` (generic credentials form)

**Files:**
- Create: `frontend/app/src/entities/authentication/ui/credentials-form.tsx`
- Create: `frontend/app/src/entities/authentication/ui/credentials-form.test.tsx`

This is the reusable form. It does NOT know which endpoint it calls — the caller passes `onSubmit`. It owns:
- Form rendering (username + password + submit button)
- Calling `onSubmit(values)`
- Calling `setToken(result)` on success
- Mapping errors to `LoginError` and showing a toast

- [ ] **Step 1: Write the failing test**

Create `frontend/app/src/entities/authentication/ui/credentials-form.test.tsx`:

```typescript
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { useAuth } from "@/entities/authentication/ui/useAuth";

import { render } from "../../../../tests/components/render";
import { CredentialsForm } from "./credentials-form";

vi.mock("@/entities/authentication/ui/useAuth");

const setToken = vi.fn();

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    accessToken: null,
    data: undefined,
    isAuthenticated: false,
    setToken,
    user: null,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("CredentialsForm", () => {
  test("renders username and password fields", async () => {
    const component = await render(<CredentialsForm onSubmit={vi.fn()} />);

    await expect.element(component.getByLabelText("Username")).toBeVisible();
    await expect.element(component.getByLabelText("Password")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Log in" })).toBeVisible();
  });

  test("calls onSubmit with the entered username and password", async () => {
    const onSubmit = vi.fn().mockResolvedValue({
      access_token: "tok",
      refresh_token: "ref",
    });

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("secret");
    await component.getByRole("button", { name: "Log in" }).click();

    expect(onSubmit).toHaveBeenCalledWith({ username: "alice", password: "secret" });
  });

  test("calls setToken with the result on success", async () => {
    const token = { access_token: "tok", refresh_token: "ref" };
    const onSubmit = vi.fn().mockResolvedValue(token);

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("secret");
    await component.getByRole("button", { name: "Log in" }).click();

    // microtask flush
    await new Promise((r) => setTimeout(r, 0));
    expect(setToken).toHaveBeenCalledWith(token);
  });

  test("shows 'Invalid username or password' toast on 401 error", async () => {
    const onSubmit = vi.fn().mockRejectedValue({ status: 401 });

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("wrong");
    await component.getByRole("button", { name: "Log in" }).click();

    await expect.element(component.getByText("Invalid username or password")).toBeVisible();
    expect(setToken).not.toHaveBeenCalled();
  });

  test("shows server-error toast on 5xx error", async () => {
    const onSubmit = vi.fn().mockRejectedValue({ status: 503 });

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);

    await component.getByLabelText("Username").fill("alice");
    await component.getByLabelText("Password").fill("secret");
    await component.getByRole("button", { name: "Log in" }).click();

    await expect.element(component.getByText("Authentication service unavailable")).toBeVisible();
  });

  test("validates required fields before submitting", async () => {
    const onSubmit = vi.fn();

    const component = await render(<CredentialsForm onSubmit={onSubmit} />);
    await component.getByRole("button", { name: "Log in" }).click();

    expect(onSubmit).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend/app && pnpm test src/entities/authentication/ui/credentials-form.test.tsx
```

Expected: FAIL — module `./credentials-form` does not exist.

- [ ] **Step 3: Implement the component**

Create `frontend/app/src/entities/authentication/ui/credentials-form.tsx`:

```typescript
import { toast } from "react-toastify";

import InputField from "@/shared/components/form/fields/input.field";
import PasswordInputField from "@/shared/components/form/fields/password-input.field";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";

import type { LoginError, UserToken } from "@/entities/authentication/types";
import { useAuth } from "@/entities/authentication/ui/useAuth";

export interface CredentialsFormProps {
  onSubmit: (values: { username: string; password: string }) => Promise<UserToken>;
  className?: string;
  submitLabel?: string;
}

function toLoginError(error: unknown): LoginError {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return { code: "network", message: "Network error — check your connection" };
  }
  const status = (error as { status?: number } | null)?.status;
  if (status === 401) {
    return { code: "invalid_credentials", message: "Invalid username or password" };
  }
  if (typeof status === "number" && status >= 500) {
    return { code: "server", message: "Authentication service unavailable" };
  }
  return { code: "unknown", message: "Could not log in" };
}

export const CredentialsForm = ({
  onSubmit,
  className,
  submitLabel = "Log in",
}: CredentialsFormProps) => {
  const { setToken } = useAuth();

  return (
    <Form
      className={classNames("w-full", className)}
      onSubmit={async (formData) => {
        const values = {
          username: formData.username.value as string,
          password: formData.password.value as string,
        };
        try {
          const result = await onSubmit(values);
          setToken(result);
        } catch (error) {
          const loginError = toLoginError(error);
          console.error("Error when logging in: ", error);
          toast(<Alert type={ALERT_TYPES.ERROR} message={loginError.message} />, {
            toastId: `alert-error-sign-in-${loginError.code}`,
          });
        }
      }}
    >
      <InputField
        name="username"
        label="Username"
        rules={{ validate: { required: isRequired } }}
        autoFocus
      />

      <PasswordInputField
        name="password"
        label="Password"
        rules={{ validate: { required: isRequired } }}
      />

      <FormSubmit className="h-10 w-full">{submitLabel}</FormSubmit>
    </Form>
  );
};
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend/app && pnpm test src/entities/authentication/ui/credentials-form.test.tsx
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/src/entities/authentication/ui/credentials-form.tsx \
        frontend/app/src/entities/authentication/ui/credentials-form.test.tsx
git commit -m "$(cat <<'EOF'
feat(auth): add CredentialsForm component

Reusable username/password form parameterized by an onSubmit callback.
Single place that maps auth errors to user-visible toasts (invalid /
network / server / unknown) and the only call site for setToken in the
interactive login flow.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — `<LocalCredentialsForm>` wrapper

**Files:**
- Create: `frontend/app/src/entities/authentication/ui/local-credentials-form.tsx`

No tests needed — it's a 5-line wrapper. The behavior is fully covered by `credentials-form.test.tsx` (with `onSubmit` mocked) and the existing `login.spec.ts` e2e.

- [ ] **Step 1: Create the wrapper**

Create `frontend/app/src/entities/authentication/ui/local-credentials-form.tsx`:

```typescript
import { CredentialsForm } from "@/entities/authentication/ui/credentials-form";
import { useLoginWithCredentials } from "@/entities/authentication/ui/queries/login-with-credentials.mutation";

export const LocalCredentialsForm = ({ className }: { className?: string }) => {
  const { mutateAsync } = useLoginWithCredentials();
  return <CredentialsForm onSubmit={mutateAsync} className={className} />;
};
```

- [ ] **Step 2: Type-check passes**

```bash
cd frontend/app && pnpm exec tsc --noEmit -p tsconfig.app.json
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/src/entities/authentication/ui/local-credentials-form.tsx
git commit -m "$(cat <<'EOF'
feat(auth): add LocalCredentialsForm wrapper

Wires the generic CredentialsForm to the local /api/auth/login mutation.
LDAP will add a sibling LdapCredentialsForm with the same shape.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — `useLastUsedMethod` hook

**Files:**
- Create: `frontend/app/src/entities/authentication/ui/use-last-used-method.ts`
- Create: `frontend/app/src/entities/authentication/ui/use-last-used-method.test.ts`

Encapsulates the "remember the last method I used" behavior. Reads/writes `localStorage[LAST_USED_METHOD_KEY]`. Falls back to the first available method if the stored value is missing or no longer available.

- [ ] **Step 1: Write the failing test**

Create `frontend/app/src/entities/authentication/ui/use-last-used-method.test.ts`:

```typescript
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { LAST_USED_METHOD_KEY } from "@/entities/authentication/constants";
import type { AuthMethod } from "@/entities/authentication/types";

import { useLastUsedMethod } from "./use-last-used-method";

const local: AuthMethod = { kind: "local", label: "Username & password" };
const sso: AuthMethod = { kind: "sso", providers: [] };

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe("useLastUsedMethod", () => {
  test("defaults to the first method when nothing is stored", () => {
    const { result } = renderHook(() => useLastUsedMethod([local, sso]));
    expect(result.current[0]).toEqual(local);
  });

  test("restores the stored method when it is still available", () => {
    localStorage.setItem(LAST_USED_METHOD_KEY, "sso");

    const { result } = renderHook(() => useLastUsedMethod([local, sso]));

    expect(result.current[0]).toEqual(sso);
  });

  test("falls back to the first method when the stored kind is no longer available", () => {
    localStorage.setItem(LAST_USED_METHOD_KEY, "ldap");

    const { result } = renderHook(() => useLastUsedMethod([local, sso]));

    expect(result.current[0]).toEqual(local);
  });

  test("setActive writes to localStorage and updates state", () => {
    const { result } = renderHook(() => useLastUsedMethod([local, sso]));

    act(() => {
      result.current[1](sso);
    });

    expect(result.current[0]).toEqual(sso);
    expect(localStorage.getItem(LAST_USED_METHOD_KEY)).toBe("sso");
  });

  test("returns null active when no methods are available", () => {
    const { result } = renderHook(() => useLastUsedMethod([]));
    expect(result.current[0]).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend/app && pnpm test src/entities/authentication/ui/use-last-used-method.test.ts
```

Expected: FAIL — module `./use-last-used-method` does not exist.

- [ ] **Step 3: Implement the hook**

Create `frontend/app/src/entities/authentication/ui/use-last-used-method.ts`:

```typescript
import { useState } from "react";

import { LAST_USED_METHOD_KEY } from "@/entities/authentication/constants";
import type { AuthMethod, AuthMethodKind } from "@/entities/authentication/types";

function pickInitial(methods: Array<AuthMethod>): AuthMethod | null {
  if (methods.length === 0) return null;
  const storedKind = localStorage.getItem(LAST_USED_METHOD_KEY) as AuthMethodKind | null;
  const found = storedKind ? methods.find((m) => m.kind === storedKind) : undefined;
  return found ?? methods[0];
}

export function useLastUsedMethod(
  methods: Array<AuthMethod>
): [AuthMethod | null, (method: AuthMethod) => void] {
  const [active, setActiveState] = useState<AuthMethod | null>(() => pickInitial(methods));

  const setActive = (method: AuthMethod) => {
    localStorage.setItem(LAST_USED_METHOD_KEY, method.kind);
    setActiveState(method);
  };

  return [active, setActive];
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend/app && pnpm test src/entities/authentication/ui/use-last-used-method.test.ts
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/src/entities/authentication/ui/use-last-used-method.ts \
        frontend/app/src/entities/authentication/ui/use-last-used-method.test.ts
git commit -m "$(cat <<'EOF'
feat(auth): add useLastUsedMethod hook

Persists the most recently selected auth method in localStorage and
falls back to the first available method when the stored value is
missing or no longer offered by the server.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — `<LoginMethodPicker>` component

**Files:**
- Create: `frontend/app/src/entities/authentication/ui/login-method-picker.tsx`
- Create: `frontend/app/src/entities/authentication/ui/login-method-picker.test.tsx`

This is the entry-point component rendered by the login page.

- [ ] **Step 1: Write the failing test**

Create `frontend/app/src/entities/authentication/ui/login-method-picker.test.tsx`:

```typescript
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { useConfig } from "@/entities/config/ui/config-provider";

import { render } from "../../../../tests/components/render";
import { LoginMethodPicker } from "./login-method-picker";

vi.mock("@/entities/config/ui/config-provider");

const ssoProvider = {
  name: "google",
  display_label: "Google",
  icon: "mdi:google",
  protocol: "oauth2",
  authorize_path: "/api/oauth2/google/authorize",
  token_path: "/api/oauth2/google/token",
};

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("LoginMethodPicker", () => {
  test("renders the local form without a toggle when local is the only method", async () => {
    vi.mocked(useConfig).mockReturnValue({
      sso: { enabled: false, providers: [] },
    } as any);

    const component = await render(<LoginMethodPicker />);

    await expect.element(component.getByLabelText("Username")).toBeVisible();
    await expect.element(component.getByLabelText("Password")).toBeVisible();
    expect(component.getByRole("button", { name: /Log in with SSO/ }).elements().length).toBe(0);
  });

  test("renders the local form and a 'Log in with SSO' toggle when SSO is available", async () => {
    vi.mocked(useConfig).mockReturnValue({
      sso: { enabled: true, providers: [ssoProvider] },
    } as any);

    const component = await render(<LoginMethodPicker />);

    // The picker defaults to SSO when available and no preference is stored
    // (preserves the existing UX from the old Login component).
    await expect.element(component.getByRole("link", { name: "Continue with Google" })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Log in with your credentials" }))
      .toBeVisible();
  });

  test("switching to credentials shows the credentials form and a 'Log in with SSO' toggle", async () => {
    vi.mocked(useConfig).mockReturnValue({
      sso: { enabled: true, providers: [ssoProvider] },
    } as any);

    const component = await render(<LoginMethodPicker />);

    await component.getByRole("button", { name: "Log in with your credentials" }).click();

    await expect.element(component.getByLabelText("Username")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Log in with SSO" })).toBeVisible();
  });

  test("restores the last-used method from localStorage", async () => {
    localStorage.setItem("auth_last_used_method", "local");
    vi.mocked(useConfig).mockReturnValue({
      sso: { enabled: true, providers: [ssoProvider] },
    } as any);

    const component = await render(<LoginMethodPicker />);

    await expect.element(component.getByLabelText("Username")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Log in with SSO" })).toBeVisible();
  });

  test("falls back gracefully when the stored method is no longer available", async () => {
    localStorage.setItem("auth_last_used_method", "ldap");
    vi.mocked(useConfig).mockReturnValue({
      sso: { enabled: false, providers: [] },
    } as any);

    const component = await render(<LoginMethodPicker />);

    await expect.element(component.getByLabelText("Username")).toBeVisible();
  });
});
```

> **Decision recorded inline:** when SSO is available and nothing is stored, the picker defaults to **SSO first** to preserve the current UX (today the `Login` component starts in SSO mode). When the user explicitly chooses credentials, that choice is persisted. The first call to `setActive` triggers the persistence.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend/app && pnpm test src/entities/authentication/ui/login-method-picker.test.tsx
```

Expected: FAIL — module `./login-method-picker` does not exist.

- [ ] **Step 3: Implement the component**

Create `frontend/app/src/entities/authentication/ui/login-method-picker.tsx`:

```typescript
import { Button } from "@infrahub/ui";

import { classNames } from "@/shared/utils/common";

import type { AuthMethod, AuthMethodKind } from "@/entities/authentication/types";
import { LocalCredentialsForm } from "@/entities/authentication/ui/local-credentials-form";
import { LoginWithSSOButtons } from "@/entities/authentication/ui/login-sso-buttons";
import { useAvailableAuthMethods } from "@/entities/authentication/ui/use-available-auth-methods";
import { useLastUsedMethod } from "@/entities/authentication/ui/use-last-used-method";

const TOGGLE_LABEL: Record<AuthMethodKind, string> = {
  local: "Log in with your credentials",
  sso: "Log in with SSO",
  // Future: ldap: "Log in with LDAP",
};

function MethodContent({ method }: { method: AuthMethod }) {
  switch (method.kind) {
    case "local":
      return <LocalCredentialsForm className="fade-in animate-in" />;
    case "sso":
      return (
        <LoginWithSSOButtons providers={method.providers} className="fade-in animate-in" />
      );
  }
}

// When multiple methods are available and no preference is stored, prefer SSO
// to preserve the existing default UX. Stored preferences override this.
function preferredDefault(methods: Array<AuthMethod>): AuthMethod {
  return methods.find((m) => m.kind === "sso") ?? methods[0];
}

export const LoginMethodPicker = () => {
  const methods = useAvailableAuthMethods();
  const [active, setActive] = useLastUsedMethod(methods);

  if (methods.length === 0 || !active) {
    return <p className="text-red-500 text-sm">No authentication method available.</p>;
  }

  // Apply the SSO-first default when the stored preference yielded the first
  // method (= localStorage was empty AND first method isn't SSO).
  const effectiveActive =
    localStorage.getItem("auth_last_used_method") === null && methods.length > 1
      ? preferredDefault(methods)
      : active;

  const others = methods.filter((m) => m.kind !== effectiveActive.kind);

  return (
    <>
      <MethodContent method={effectiveActive} />
      {others.map((m) => (
        <Button
          key={m.kind}
          variant="ghost"
          onPress={() => setActive(m)}
          className={classNames(
            "text-cyan-900 text-sm",
            "data-hovered:bg-transparent data-hovered:underline"
          )}
        >
          {TOGGLE_LABEL[m.kind]}
        </Button>
      ))}
    </>
  );
};
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend/app && pnpm test src/entities/authentication/ui/login-method-picker.test.tsx
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/src/entities/authentication/ui/login-method-picker.tsx \
        frontend/app/src/entities/authentication/ui/login-method-picker.test.tsx
git commit -m "$(cat <<'EOF'
feat(auth): add LoginMethodPicker component

Replaces the binary SSO/credentials toggle with an N-method picker that
remembers the last-used method, defaults to SSO when available and no
preference is stored (preserves existing UX), and renders only the
active method plus toggles for the others.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7 — Wire `<LoginMethodPicker>` into the login page; delete `login.tsx`

**Files:**
- Modify: `frontend/app/src/pages/login.tsx`
- Delete: `frontend/app/src/entities/authentication/ui/login.tsx`

- [ ] **Step 1: Update the login page**

Replace the contents of `frontend/app/src/pages/login.tsx` with:

```typescript
import { Navigate, useLocation } from "react-router";

import InfrahubLogo from "@/assets/Infrahub-SVG-hori.svg?react";

import { LoginMethodPicker } from "@/entities/authentication/ui/login-method-picker";
import { useAuth } from "@/entities/authentication/ui/useAuth";

function LoginPage() {
  const location = useLocation();
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    const from = (location.state?.from?.pathname || "/") + (location.state?.from?.search ?? "");
    return <Navigate to={from} replace />;
  }

  return (
    <div className="h-screen w-screen overflow-auto bg-stone-100 py-[25vh]">
      <div className="m-auto flex w-full max-w-sm flex-col items-center gap-6">
        <InfrahubLogo className="h-12" />

        <h1 className="font-semibold text-neutral-900 text-xl">Log in to your account</h1>

        <LoginMethodPicker />

        {location?.state?.errors?.map(
          (error: { extensions: { code: number }; message: string }, index: number) => (
            <p key={index} className="mt-2 text-red-500 text-sm">
              ({error.extensions.code}) {error.message}
            </p>
          )
        )}
      </div>
    </div>
  );
}

export const Component = LoginPage;
```

- [ ] **Step 2: Delete the old `login.tsx`**

```bash
rm frontend/app/src/entities/authentication/ui/login.tsx
```

- [ ] **Step 3: Confirm no stale imports**

```bash
grep -rn "entities/authentication/ui/login\"" frontend/app/src || true
grep -rn "from \"@/entities/authentication/ui/login\"" frontend/app/src || true
```

Expected: no matches.

- [ ] **Step 4: Type-check and run all auth tests**

```bash
cd frontend/app && pnpm exec tsc --noEmit -p tsconfig.app.json
cd frontend/app && pnpm test src/entities/authentication
```

Expected: type-check exits 0; all auth tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/src/pages/login.tsx \
        frontend/app/src/entities/authentication/ui/login.tsx
git commit -m "$(cat <<'EOF'
refactor(auth): use LoginMethodPicker on the login page

Removes the old Login/LoginForm pair (replaced by LoginMethodPicker +
LocalCredentialsForm). No external behavior change — Playwright login
selectors are preserved.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8 — Stop persisting tokens inside the local-credentials domain function

**Files:**
- Modify: `frontend/app/src/entities/authentication/domain/login-with-credentials.ts`

After this change `saveTokensInLocalStorage` is called from exactly two places:
1. `useAuth.setToken` (interactive flows)
2. `domain/refresh-access-token.ts` (background refresh, runs outside React)

- [ ] **Step 1: Modify the domain function**

Replace the contents of `frontend/app/src/entities/authentication/domain/login-with-credentials.ts` with:

```typescript
import { apiClient } from "@/shared/api/rest/client";

import type { UserToken } from "@/entities/authentication/types";

export type LoginWithCredentialsParams = {
  username: string;
  password: string;
};

export type LoginWithCredentials = (params: LoginWithCredentialsParams) => Promise<UserToken>;

export const loginWithCredentials: LoginWithCredentials = async (params) => {
  const { data, error } = await apiClient.POST("/api/auth/login", {
    body: params,
  });

  if (error) throw error;

  return data;
};
```

- [ ] **Step 2: Confirm persistence call sites**

```bash
grep -rn "saveTokensInLocalStorage" frontend/app/src
```

Expected: exactly two call sites — `useAuth.tsx` and `domain/refresh-access-token.ts`. (The `utils.ts` declaration of the function itself is NOT a call.)

- [ ] **Step 3: Run all auth tests + login e2e**

```bash
cd frontend/app && pnpm test src/entities/authentication
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/src/entities/authentication/domain/login-with-credentials.ts
git commit -m "$(cat <<'EOF'
refactor(auth): make useAuth the single token-persistence site

loginWithCredentials no longer writes tokens to localStorage. The
AuthContext.setToken setter is now the only writer during interactive
login; refresh-access-token keeps its own writer because it runs
outside React.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9 — Full verification

**Files:** none

- [ ] **Step 1: Format**

```bash
cd frontend/app && pnpm biome:fix
```

Expected: no errors. If files were reformatted, stage and amend or create a follow-up commit:

```bash
git diff --quiet || (git add -u && git commit -m "$(cat <<'EOF'
style(auth): apply biome formatting

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)")
```

- [ ] **Step 2: Type-check**

```bash
cd frontend/app && pnpm exec tsc --noEmit -p tsconfig.app.json
```

Expected: exits 0.

- [ ] **Step 3: Unit tests (full suite)**

```bash
cd frontend/app && pnpm test
```

Expected: all PASS, including the new auth tests.

- [ ] **Step 4: E2E — login flow only**

The Playwright `login.spec.ts` expects a running backend stack. Run only this spec, NOT the full e2e suite:

```bash
cd frontend/app && pnpm test:e2e login.spec.ts
```

Expected: all `/login` tests PASS — covers SSO toggle, credentials login, error toast, redirect-after-login, logout, and refresh-on-401.

- [ ] **Step 5: Acceptance verification**

Manually confirm each spec acceptance criterion:

1. `pnpm test:e2e login.spec.ts` passes without modification. ✔ (Step 4)
2. `pnpm biome:fix` and `pnpm test` pass. ✔ (Steps 1, 3)
3. `saveTokensInLocalStorage` is called from exactly two places: `useAuth.setToken` and `domain/refresh-access-token.ts`. ✔ (Task 8 Step 2)
4. Adding LDAP requires only: 1 domain file, 1 mutation file, 1 wrapper component, 1 `AuthMethod` branch, 1 push in `useAvailableAuthMethods`, 1 label case in `LoginMethodPicker`. ✔ (verified by inspection of the touched files)
5. Tokens are written once per interactive login. ✔ (Task 8)
6. Distinct error messages for invalid credentials / network / server / unknown. ✔ (Task 3 tests)

- [ ] **Step 6: Final commit (only if anything stages from biome)**

Already covered in Step 1. Otherwise no additional commit.

---

## Out-of-scope reminders

The following are explicitly out of scope per the spec — do NOT touch them in this work:

- `domain/refresh-access-token.ts` — keeps `window.location.reload()` and its own persistence.
- `pages/auth-callback.tsx` — keeps the OAuth/OIDC-specific `code`/`state` handling.
- `domain/logout.ts` — unchanged.
- `ui/require-auth.tsx` — unchanged.
- Backend — no changes.

## Risks and mitigations

- **Playwright selector regression.** The e2e tests look up buttons by text: `"Log in"`, `"Log in with SSO"`, `"Log in with your credentials"`. Task 6 keeps those exact strings via `TOGGLE_LABEL` and `CredentialsForm`'s default `submitLabel`. Step 4 of Task 9 validates this.
- **`vitest-browser-react` API drift.** Tests use `await render(...)` then `component.getByXxx(...)` and `await expect.element(...).toBeVisible()`. This matches the existing pattern in `about-modal.test.tsx` and `account-logged-in-event-title.test.tsx`.
- **Stored last-used-method default behavior.** Task 6's implementation preserves "SSO first when no preference stored" only when SSO is available. A user who previously saw the SSO screen by default will continue to see it until they pick credentials explicitly. This is intentional and tested.
