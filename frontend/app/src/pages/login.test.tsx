import { afterEach, describe, expect, test, vi } from "vitest";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { useConfig } from "@/entities/config/ui/config-provider";

import { render } from "../../tests/components/render";
import { generateConfigWithInstance } from "../../tests/fake/config";
import { Component as LoginPage } from "./login";

vi.mock("@/entities/authentication/ui/auth-provider");
vi.mock("@/entities/config/ui/config-provider");
vi.mock("@/entities/authentication/ui/login-method-picker", () => ({
  LoginMethodPicker: () => <form aria-label="Log in">login form</form>,
}));

const unauthenticated: ReturnType<typeof useAuth> = {
  accessToken: "",
  isAuthenticated: false,
  setToken: () => {},
  user: null,
};

describe("LoginPage", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("shows the instance color bar above the page and the badge above the logo", async () => {
    // GIVEN
    vi.mocked(useAuth).mockReturnValue(unauthenticated);
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance("QA", "RED"));

    // WHEN
    const component = await render(<LoginPage />);

    // THEN
    const bar = component.getByTestId("instance-color-bar").element();
    const badge = component.getByText("QA").element();
    const heading = component.getByRole("heading", { name: "Log in to your account" }).element();
    expect(bar.parentElement?.firstElementChild).toBe(bar);
    expect(bar.nextElementSibling?.contains(heading)).toBe(true);
    expect(badge.parentElement?.firstElementChild).toBe(badge);
    expect(badge.nextElementSibling?.tagName.toLowerCase()).toBe("svg");
  });

  test("shows neither the bar nor the badge when no instance identity is set", async () => {
    // GIVEN
    vi.mocked(useAuth).mockReturnValue(unauthenticated);
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance(null, null));

    // WHEN
    const component = await render(<LoginPage />);

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Log in to your account" }))
      .toBeVisible();
    expect(component.getByTestId("instance-color-bar").query()).toBeNull();
    expect(component.getByTestId("instance-badge").query()).toBeNull();
  });
});
