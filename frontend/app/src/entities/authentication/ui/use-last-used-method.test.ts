import { afterEach, beforeEach, describe, expect, test } from "vitest";
import { renderHook } from "vitest-browser-react";

import type { AuthMethod } from "@/entities/authentication/auth-methods";
import { LAST_USED_METHOD_KEY } from "@/entities/authentication/constants";

import { useLastUsedMethod } from "./use-last-used-method";

const local: AuthMethod = { kind: "local" };
const sso: AuthMethod = { kind: "sso", providers: [] };

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe("useLastUsedMethod", () => {
  test("defaults to the first method when nothing is stored", async () => {
    const { result } = await renderHook(() => useLastUsedMethod([local, sso]));
    expect(result.current[0]).toEqual(local);
  });

  test("restores the stored method when it is still available", async () => {
    localStorage.setItem(LAST_USED_METHOD_KEY, "sso");

    const { result } = await renderHook(() => useLastUsedMethod([local, sso]));

    expect(result.current[0]).toEqual(sso);
  });

  test("falls back to the first method when the stored kind is no longer available", async () => {
    localStorage.setItem(LAST_USED_METHOD_KEY, "ldap");

    const { result } = await renderHook(() => useLastUsedMethod([local, sso]));

    expect(result.current[0]).toEqual(local);
  });

  test("setActive writes to localStorage and updates state", async () => {
    const hook = await renderHook(() => useLastUsedMethod([local, sso]));

    await hook.act(() => {
      hook.result.current[1](sso);
    });

    expect(hook.result.current[0]).toEqual(sso);
    expect(localStorage.getItem(LAST_USED_METHOD_KEY)).toBe("sso");
  });

  test("returns null active when no methods are available", async () => {
    const { result } = await renderHook(() => useLastUsedMethod([]));
    expect(result.current[0]).toBeNull();
  });

  test("uses defaultMethod when nothing is stored and a default is provided", async () => {
    const hook = await renderHook(() => useLastUsedMethod([local, sso], sso));
    expect(hook.result.current[0]).toEqual(sso);
  });

  test("falls back when the selected method disappears between renders", async () => {
    localStorage.setItem(LAST_USED_METHOD_KEY, "sso");

    const hook = await renderHook<Array<AuthMethod>, ReturnType<typeof useLastUsedMethod>>(
      (methods = [local, sso]) => useLastUsedMethod(methods),
      { initialProps: [local, sso] }
    );

    expect(hook.result.current[0]).toEqual(sso);

    await hook.rerender([local]);

    expect(hook.result.current[0]).toEqual(local);
  });

  test("reflects updated method data (e.g. SSO providers) on rerender", async () => {
    const ssoEmpty: AuthMethod = { kind: "sso", providers: [] };
    const ssoFull: AuthMethod = {
      kind: "sso",
      providers: [
        {
          name: "google",
          display_label: "Google",
          icon: "",
          protocol: "oauth2",
          authorize_path: "/auth/google",
          token_path: "/token/google",
        },
      ],
    };
    localStorage.setItem(LAST_USED_METHOD_KEY, "sso");

    const hook = await renderHook<Array<AuthMethod>, ReturnType<typeof useLastUsedMethod>>(
      (methods = [local, ssoEmpty]) => useLastUsedMethod(methods),
      { initialProps: [local, ssoEmpty] }
    );

    expect(hook.result.current[0]).toEqual(ssoEmpty);

    await hook.rerender([local, ssoFull]);

    expect(hook.result.current[0]).toEqual(ssoFull);
  });
});
