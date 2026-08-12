import { beforeEach, describe, expect, test, vi } from "vitest";

import { AuthContext } from "@/entities/authentication/ui/auth-provider";
import { getAppInfo } from "@/entities/config/domain/use-cases/get-app-info";
import { ConfigContext } from "@/entities/config/ui/config-provider";
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

describe("AccountMenu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
});
