import { describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import type { ConfigAPI } from "@/entities/config/types";
import { useConfig } from "@/entities/config/ui/config-provider";

import { useAvailableAuthMethods } from "./use-available-auth-methods";

vi.mock("@/entities/config/ui/config-provider");

const configWithSso = (sso: Partial<ConfigAPI["sso"]>): ConfigAPI =>
  ({ sso }) as unknown as ConfigAPI;

describe("useAvailableAuthMethods", () => {
  test("returns [local] when SSO is disabled", async () => {
    vi.mocked(useConfig).mockReturnValue(configWithSso({ enabled: false, providers: [] }));

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([{ kind: "local" }]);
  });

  test("returns [local, sso] when SSO is enabled with at least one provider", async () => {
    const providers = [
      {
        name: "google",
        display_label: "Google",
        icon: "mdi:google",
        protocol: "oauth2" as const,
        authorize_path: "/api/oauth2/google/authorize",
        token_path: "/api/oauth2/google/token",
      },
    ];
    vi.mocked(useConfig).mockReturnValue(configWithSso({ enabled: true, providers }));

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([{ kind: "local" }, { kind: "sso", providers }]);
  });

  test("returns [local] when SSO is enabled but providers list is empty", async () => {
    vi.mocked(useConfig).mockReturnValue(configWithSso({ enabled: true, providers: [] }));

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([{ kind: "local" }]);
  });

  test("returns [local] when SSO is enabled but providers is undefined", async () => {
    vi.mocked(useConfig).mockReturnValue(configWithSso({ enabled: true }));

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([{ kind: "local" }]);
  });
});
