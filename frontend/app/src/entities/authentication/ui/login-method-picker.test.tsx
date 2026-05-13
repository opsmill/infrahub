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
