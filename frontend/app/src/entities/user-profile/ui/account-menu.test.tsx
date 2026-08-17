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

function renderAccountMenu() {
  return render(
    <ConfigContext value={config}>
      <AuthContext value={auth}>
        <AccountMenu />
      </AuthContext>
    </ConfigContext>
  );
}

function renderAccountMenuWithTheme(darkTheme: boolean) {
  return render(
    <ConfigContext value={{ ...config, experimental_features: { dark_theme: darkTheme } }}>
      <ThemeProvider>
        <AuthContext value={auth}>
          <AccountMenu />
        </AuthContext>
      </ThemeProvider>
    </ConfigContext>
  );
}

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

    const component = await renderAccountMenu();
    await component.getByTestId("authenticated-menu-trigger").click();

    const menuItem = component.getByRole("menuitem", { name: "Global preferences" });
    await expect.element(menuItem).toBeVisible();
    await expect
      .element(menuItem)
      .toHaveAttribute("href", expect.stringContaining("/global-preferences"));
  });

  test("hides the Global preferences menu item when the user cannot manage them", async () => {
    vi.mocked(hasGlobalPermission).mockResolvedValue(false);

    const component = await renderAccountMenu();
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

  test("offers the theme switch, marked alpha, when the deployment enables it", async () => {
    vi.mocked(hasGlobalPermission).mockResolvedValue(false);

    const component = await renderAccountMenuWithTheme(true);
    await component.getByTestId("authenticated-menu-trigger").click();

    // The default is dark, so the switch offers the way back out.
    const menuItem = component.getByRole("menuitem", { name: /Light theme/ });
    await expect.element(menuItem).toBeVisible();
    await expect.element(menuItem).toHaveTextContent("alpha");

    await menuItem.click();

    await expect.poll(() => document.documentElement.classList.contains("dark")).toBe(false);
  });

  test("hides the theme switch when the deployment does not enable it", async () => {
    vi.mocked(hasGlobalPermission).mockResolvedValue(false);

    const component = await renderAccountMenuWithTheme(false);
    await component.getByTestId("authenticated-menu-trigger").click();

    await expect
      .element(component.getByRole("menuitem", { name: "Account settings" }))
      .toBeVisible();
    expect(component.getByRole("menuitem", { name: /theme/i }).elements()).toHaveLength(0);
  });
});
