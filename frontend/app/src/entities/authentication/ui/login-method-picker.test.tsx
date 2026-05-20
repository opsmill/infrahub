import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { LAST_USED_METHOD_KEY } from "@/entities/authentication/constants";
import type { ConfigAPI, SSOProvider } from "@/entities/config/types";
import { useConfig } from "@/entities/config/ui/config-provider";

import { render } from "../../../../tests/components/render";
import { LoginMethodPicker } from "./login-method-picker";

vi.mock("@/entities/config/ui/config-provider");

const ssoProvider: SSOProvider = {
  name: "google",
  display_label: "Google",
  icon: "mdi:google",
  protocol: "oauth2",
  authorize_path: "/api/oauth2/google/authorize",
  token_path: "/api/oauth2/google/token",
};

const configWithSso = (sso: Partial<ConfigAPI["sso"]>): ConfigAPI =>
  ({ sso }) as unknown as ConfigAPI;

const configWith = ({
  sso,
  ldap,
}: {
  sso?: Partial<ConfigAPI["sso"]>;
  ldap?: Partial<ConfigAPI["ldap"]>;
}): ConfigAPI => ({ sso, ldap }) as unknown as ConfigAPI;

const ldapConfig = {
  enabled: true,
  display_label: "Sign in with Corp AD",
  icon: "mdi:microsoft-windows",
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
    vi.mocked(useConfig).mockReturnValue(configWithSso({ enabled: false, providers: [] }));

    const component = await render(<LoginMethodPicker />);

    await expect.element(component.getByLabelText("Username")).toBeVisible();
    await expect.element(component.getByLabelText("Password")).toBeVisible();
    expect(component.getByRole("button", { name: /Log in with SSO/ }).elements().length).toBe(0);
  });

  test("renders the local form and a 'Log in with SSO' toggle when SSO is available", async () => {
    vi.mocked(useConfig).mockReturnValue(
      configWithSso({ enabled: true, providers: [ssoProvider] })
    );

    const component = await render(<LoginMethodPicker />);

    // The picker defaults to SSO when available and no preference is stored
    // (preserves the existing UX from the old Login component).
    await expect
      .element(component.getByRole("link", { name: "Continue with Google" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Log in with your credentials" }))
      .toBeVisible();
  });

  test("switching to credentials shows the credentials form and a 'Log in with SSO' toggle", async () => {
    vi.mocked(useConfig).mockReturnValue(
      configWithSso({ enabled: true, providers: [ssoProvider] })
    );

    const component = await render(<LoginMethodPicker />);

    await component.getByRole("button", { name: "Log in with your credentials" }).click();

    await expect.element(component.getByLabelText("Username")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Log in with SSO" })).toBeVisible();
  });

  test("restores the last-used method from localStorage", async () => {
    localStorage.setItem(LAST_USED_METHOD_KEY, "local");
    vi.mocked(useConfig).mockReturnValue(
      configWithSso({ enabled: true, providers: [ssoProvider] })
    );

    const component = await render(<LoginMethodPicker />);

    await expect.element(component.getByLabelText("Username")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Log in with SSO" })).toBeVisible();
  });

  test("falls back gracefully when the stored method is no longer available", async () => {
    localStorage.setItem(LAST_USED_METHOD_KEY, "ldap");
    vi.mocked(useConfig).mockReturnValue(configWithSso({ enabled: false, providers: [] }));

    const component = await render(<LoginMethodPicker />);

    await expect.element(component.getByLabelText("Username")).toBeVisible();
  });

  test("renders local form and an LDAP toggle showing the custom display label when LDAP is enabled", async () => {
    vi.mocked(useConfig).mockReturnValue(configWith({ ldap: ldapConfig }));

    const component = await render(<LoginMethodPicker />);

    // Local is the default when no SSO is configured (no method has preferDefault).
    await expect.element(component.getByLabelText("Username")).toBeVisible();
    await expect.element(component.getByLabelText("Password")).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Sign in with Corp AD" }))
      .toBeVisible();
    expect(component.getByRole("button", { name: /Log in with SSO/ }).elements().length).toBe(0);
  });

  test("switching to LDAP shows the LDAP form with the custom submit label and a local toggle", async () => {
    vi.mocked(useConfig).mockReturnValue(configWith({ ldap: ldapConfig }));

    const component = await render(<LoginMethodPicker />);

    await component.getByRole("button", { name: "Sign in with Corp AD" }).click();

    await expect.element(component.getByLabelText("Username")).toBeVisible();
    await expect.element(component.getByLabelText("Password")).toBeVisible();
    // The submit button in the LDAP form uses the configured display_label.
    await expect
      .element(component.getByRole("button", { name: "Sign in with Corp AD" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Log in with your credentials" }))
      .toBeVisible();
  });

  test("with SSO and LDAP both enabled, SSO is the default and local + LDAP appear as toggles", async () => {
    vi.mocked(useConfig).mockReturnValue(
      configWith({ sso: { enabled: true, providers: [ssoProvider] }, ldap: ldapConfig })
    );

    const component = await render(<LoginMethodPicker />);

    await expect
      .element(component.getByRole("link", { name: "Continue with Google" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Log in with your credentials" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Sign in with Corp AD" }))
      .toBeVisible();
  });

  test("switching from SSO to LDAP renders the LDAP form and offers SSO and local toggles", async () => {
    vi.mocked(useConfig).mockReturnValue(
      configWith({ sso: { enabled: true, providers: [ssoProvider] }, ldap: ldapConfig })
    );

    const component = await render(<LoginMethodPicker />);

    await component.getByRole("button", { name: "Sign in with Corp AD" }).click();

    await expect.element(component.getByLabelText("Username")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Log in with SSO" })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Log in with your credentials" }))
      .toBeVisible();
  });

  test("restores LDAP from localStorage when it is configured", async () => {
    localStorage.setItem(LAST_USED_METHOD_KEY, "ldap");
    vi.mocked(useConfig).mockReturnValue(
      configWith({ sso: { enabled: true, providers: [ssoProvider] }, ldap: ldapConfig })
    );

    const component = await render(<LoginMethodPicker />);

    // The active method is LDAP — its form is rendered, with the SSO link absent.
    await expect.element(component.getByLabelText("Username")).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Sign in with Corp AD" }))
      .toBeVisible();
    expect(component.getByRole("link", { name: "Continue with Google" }).elements().length).toBe(0);
    await expect.element(component.getByRole("button", { name: "Log in with SSO" })).toBeVisible();
  });

  test("renders multiple SSO provider buttons when several providers are configured", async () => {
    const githubProvider: SSOProvider = {
      name: "github",
      display_label: "GitHub",
      icon: "mdi:github",
      protocol: "oauth2",
      authorize_path: "/api/oauth2/github/authorize",
      token_path: "/api/oauth2/github/token",
    };
    vi.mocked(useConfig).mockReturnValue(
      configWithSso({ enabled: true, providers: [ssoProvider, githubProvider] })
    );

    const component = await render(<LoginMethodPicker />);

    await expect
      .element(component.getByRole("link", { name: "Continue with Google" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "Continue with GitHub" }))
      .toBeVisible();
  });
});
