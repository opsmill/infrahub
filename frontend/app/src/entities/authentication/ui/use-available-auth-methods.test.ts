import { renderHook } from "vitest-browser-react";
import { describe, expect, test, vi } from "vitest";

import { useConfig } from "@/entities/config/ui/config-provider";

import { useAvailableAuthMethods } from "./use-available-auth-methods";

vi.mock("@/entities/config/ui/config-provider");

describe("useAvailableAuthMethods", () => {
  test("returns [local] when SSO is disabled", async () => {
    vi.mocked(useConfig).mockReturnValue({
      sso: { enabled: false, providers: [] },
    } as any);

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([{ kind: "local", label: "Username & password" }]);
  });

  test("returns [local, sso] when SSO is enabled with at least one provider", async () => {
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

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([
      { kind: "local", label: "Username & password" },
      { kind: "sso", providers },
    ]);
  });

  test("returns [local] when SSO is enabled but providers list is empty", async () => {
    vi.mocked(useConfig).mockReturnValue({
      sso: { enabled: true, providers: [] },
    } as any);

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([{ kind: "local", label: "Username & password" }]);
  });

  test("returns [local] when SSO is enabled but providers is undefined", async () => {
    vi.mocked(useConfig).mockReturnValue({
      sso: { enabled: true },
    } as any);

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([{ kind: "local", label: "Username & password" }]);
  });
});
