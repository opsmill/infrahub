import { afterEach, beforeEach, describe, expect, test } from "vitest";
import { renderHook } from "vitest-browser-react";

import { LAST_USED_METHOD_KEY } from "@/entities/authentication/constants";
import type { AuthMethod } from "@/entities/authentication/types";

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
});
