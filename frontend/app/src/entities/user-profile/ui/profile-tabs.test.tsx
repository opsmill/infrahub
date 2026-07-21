import { beforeEach, describe, expect, test, vi } from "vitest";

import { hasGlobalPermission } from "@/entities/permission/domain/use-cases/has-global-permission";

import { render } from "../../../../tests/components/render";
import { ProfileTabs } from "./profile-tabs";

vi.mock("@/entities/permission/domain/use-cases/has-global-permission");

function mockCanManage(canManage: boolean) {
  vi.mocked(hasGlobalPermission).mockResolvedValue(canManage);
}

describe("ProfileTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders the core profile tabs", async () => {
    mockCanManage(false);

    const component = await render(<ProfileTabs />);

    await expect.element(component.getByRole("link", { name: "Profile" })).toBeVisible();
    await expect.element(component.getByRole("link", { name: "Tokens" })).toBeVisible();
    await expect.element(component.getByRole("link", { name: "Password" })).toBeVisible();
  });

  test("hides the Global preferences tab when the user cannot manage them", async () => {
    mockCanManage(false);

    const component = await render(<ProfileTabs />);

    await expect.element(component.getByRole("link", { name: "Password" })).toBeVisible();
    expect(component.getByRole("link", { name: "Global preferences" }).elements()).toHaveLength(0);
  });

  test("shows the Global preferences tab when the user can manage them", async () => {
    mockCanManage(true);

    const component = await render(<ProfileTabs />);

    await expect.element(component.getByRole("link", { name: "Global preferences" })).toBeVisible();
  });
});
