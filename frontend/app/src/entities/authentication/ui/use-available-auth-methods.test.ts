import { describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import type { ConfigAPI } from "@/entities/config/types";
import { useConfig } from "@/entities/config/ui/config-provider";

import { useAvailableAuthMethods } from "./use-available-auth-methods";

vi.mock("@/entities/config/ui/config-provider");

const configWithSso = (sso: Partial<ConfigAPI["sso"]>): ConfigAPI =>
  ({ sso }) as unknown as ConfigAPI;

const configWithLdap = (ldap: Partial<ConfigAPI["ldap"]>): ConfigAPI =>
  ({ ldap }) as unknown as ConfigAPI;

const configWith = ({
  sso,
  ldap,
}: {
  sso?: Partial<ConfigAPI["sso"]>;
  ldap?: Partial<ConfigAPI["ldap"]>;
}): ConfigAPI => ({ sso, ldap }) as unknown as ConfigAPI;

const googleProvider = {
  name: "google",
  display_label: "Google",
  icon: "mdi:google",
  protocol: "oauth2" as const,
  authorize_path: "/api/oauth2/google/authorize",
  token_path: "/api/oauth2/google/token",
};

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

  test("returns [local] when LDAP is disabled", async () => {
    vi.mocked(useConfig).mockReturnValue(
      configWithLdap({ enabled: false, display_label: "Sign in with LDAP", icon: "mdi:ldap" })
    );

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([{ kind: "local" }]);
  });

  test("returns [local, ldap] when LDAP is enabled, threading display_label and icon", async () => {
    vi.mocked(useConfig).mockReturnValue(
      configWithLdap({
        enabled: true,
        display_label: "Sign in with Corp AD",
        icon: "mdi:microsoft-windows",
      })
    );

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([
      { kind: "local" },
      { kind: "ldap", displayLabel: "Sign in with Corp AD", icon: "mdi:microsoft-windows" },
    ]);
  });

  test("returns [local, sso, ldap] in registry order when SSO and LDAP are both enabled", async () => {
    vi.mocked(useConfig).mockReturnValue(
      configWith({
        sso: { enabled: true, providers: [googleProvider] },
        ldap: { enabled: true, display_label: "Sign in with Corp AD", icon: "mdi:ldap" },
      })
    );

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([
      { kind: "local" },
      { kind: "sso", providers: [googleProvider] },
      { kind: "ldap", displayLabel: "Sign in with Corp AD", icon: "mdi:ldap" },
    ]);
  });

  test("returns [local, ldap] when LDAP is enabled but SSO has no providers", async () => {
    vi.mocked(useConfig).mockReturnValue(
      configWith({
        sso: { enabled: true, providers: [] },
        ldap: { enabled: true, display_label: "Sign in with LDAP", icon: "mdi:ldap" },
      })
    );

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([
      { kind: "local" },
      { kind: "ldap", displayLabel: "Sign in with LDAP", icon: "mdi:ldap" },
    ]);
  });

  test("returns [local, sso] when SSO is enabled and LDAP is disabled", async () => {
    vi.mocked(useConfig).mockReturnValue(
      configWith({
        sso: { enabled: true, providers: [googleProvider] },
        ldap: { enabled: false, display_label: "Sign in with LDAP", icon: "mdi:ldap" },
      })
    );

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([
      { kind: "local" },
      { kind: "sso", providers: [googleProvider] },
    ]);
  });

  test("returns [local] when both SSO and LDAP are disabled", async () => {
    vi.mocked(useConfig).mockReturnValue(
      configWith({
        sso: { enabled: false, providers: [] },
        ldap: { enabled: false, display_label: "Sign in with LDAP", icon: "mdi:ldap" },
      })
    );

    const { result } = await renderHook(() => useAvailableAuthMethods());

    expect(result.current).toEqual([{ kind: "local" }]);
  });
});
