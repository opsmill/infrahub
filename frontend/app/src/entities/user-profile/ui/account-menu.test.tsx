import { beforeEach, describe, expect, test, vi } from "vitest";

import { AuthContext } from "@/entities/authentication/ui/auth-provider";
import { getAppInfo } from "@/entities/config/domain/use-cases/get-app-info";
import { ConfigContext } from "@/entities/config/ui/config-provider";
import { ThemeProvider } from "@/entities/config/ui/theme-provider";
import { MANAGE_GLOBAL_PREFERENCES } from "@/entities/permission/domain/model/permission";
import { hasGlobalPermission } from "@/entities/permission/domain/use-cases/has-global-permission";
import { getAccountProfile } from "@/entities/user-profile/domain/use-cases/get-account-profile";

import { render } from "../../../../tests/components/render";
import { AccountMenu } from "./account-menu";

vi.mock("@/entities/permission/domain/use-cases/has-global-permission");
vi.mock("@/entities/user-profile/domain/use-cases/get-account-profile");
vi.mock("@/entities/config/domain/use-cases/get-app-info");

const auth = {
  isAuthenticated: true,
  accessToken: "t",
  setToken: () => {},
  user: { id: "u" },
};

const config = { installation_type: "community" } as any;

describe("AccountMenu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // The theme persists to storage and to the document element, both of which outlive a render.
    localStorage.clear();
    document.documentElement.classList.remove("dark");
    vi.mocked(getAccountProfile).mockResolvedValue({
      name: { value: "admin" },
      label: { value: "Admin" },
    } as any);
    vi.mocked(getAppInfo).mockResolvedValue({
      version: "1.8.4",
      deployment_id: "abc-123-def",
    });
  });

  test("shows the Global preferences menu item when the user can manage them", async () => {
    vi.mocked(hasGlobalPermission).mockResolvedValue(true);

    const component = await render(
      <ConfigContext value={config}>
        <ThemeProvider>
          <AuthContext value={auth}>
            <AccountMenu />
          </AuthContext>
        </ThemeProvider>
      </ConfigContext>
    );
    await component.getByTestId("authenticated-menu-trigger").click();

    const menuItem = component.getByRole("menuitem", { name: "Global preferences" });
    await expect.element(menuItem).toBeVisible();
    await expect
      .element(menuItem)
      .toHaveAttribute("href", expect.stringContaining("/global-preferences"));
  });

  test("hides the Global preferences menu item when the user cannot manage them", async () => {
    vi.mocked(hasGlobalPermission).mockResolvedValue(false);

    const component = await render(
      <ConfigContext value={config}>
        <ThemeProvider>
          <AuthContext value={auth}>
            <AccountMenu />
          </AuthContext>
        </ThemeProvider>
      </ConfigContext>
    );
    await component.getByTestId("authenticated-menu-trigger").click();

    await vi.waitFor(() => {
      expect(hasGlobalPermission).toHaveBeenCalledWith(MANAGE_GLOBAL_PREFERENCES);
    });
    await expect
      .element(component.getByRole("menuitem", { name: "Account settings" }))
      .toBeVisible();
    expect(component.getByRole("menuitem", { name: "Global preferences" }).elements()).toHaveLength(
      0
    );
  });

  test("names the choice on the Theme item and checks it in the submenu, tagging only dark", async () => {
    // GIVEN
    vi.mocked(hasGlobalPermission).mockResolvedValue(false);
    localStorage.setItem("infrahub.theme.choice", "dark");
    const component = await render(
      <ConfigContext value={config}>
        <ThemeProvider>
          <AuthContext value={auth}>
            <AccountMenu />
          </AuthContext>
        </ThemeProvider>
      </ConfigContext>
    );

    // WHEN
    await component.getByTestId("authenticated-menu-trigger").click();
    const themeItem = component.getByRole("menuitem", { name: "Theme", exact: true });
    await themeItem.click();

    // THEN
    await expect.element(themeItem).toHaveTextContent("Dark");
    const dark = component.getByRole("menuitemradio", { name: "Dark", exact: true });
    await expect.element(dark).toHaveAttribute("aria-checked", "true");
    await expect.element(dark).toHaveTextContent("alpha");
    for (const name of ["Light", "System"]) {
      const option = component.getByRole("menuitemradio", { name, exact: true });
      await expect.element(option).toHaveAttribute("aria-checked", "false");
      await expect.element(option).not.toHaveTextContent("alpha");
    }
  });

  test("choosing System follows the desktop and stores the choice", async () => {
    // GIVEN
    vi.mocked(hasGlobalPermission).mockResolvedValue(false);
    expect(window.matchMedia("(prefers-color-scheme: dark)").matches).toBe(false);
    localStorage.setItem("infrahub.theme.choice", "dark");
    const component = await render(
      <ConfigContext value={config}>
        <ThemeProvider>
          <AuthContext value={auth}>
            <AccountMenu />
          </AuthContext>
        </ThemeProvider>
      </ConfigContext>
    );
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    // WHEN
    await component.getByTestId("authenticated-menu-trigger").click();
    await component.getByRole("menuitem", { name: "Theme", exact: true }).click();
    await component.getByRole("menuitemradio", { name: "System", exact: true }).click();

    // THEN
    await expect.poll(() => document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("infrahub.theme.choice")).toBe("system");
  });
});
