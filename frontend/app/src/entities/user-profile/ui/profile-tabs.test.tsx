import type { UseQueryResult } from "@tanstack/react-query";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { useCanManageGlobalPreferences } from "@/entities/permission/ui/queries/use-can-manage-global-preferences";

import { render } from "../../../../tests/components/render";
import { ProfileTabs } from "./profile-tabs";

vi.mock("@/entities/permission/ui/queries/use-can-manage-global-preferences", () => ({
  useCanManageGlobalPreferences: vi.fn(),
}));

function mockCanEdit(canManageGlobalPreferences: boolean) {
  vi.mocked(useCanManageGlobalPreferences).mockReturnValue({
    isPending: false,
    error: null,
    data: canManageGlobalPreferences,
  } as UseQueryResult<boolean>);
}

describe("ProfileTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders the core profile tabs without a standalone Preferences tab", async () => {
    mockCanEdit(false);

    const component = await render(<ProfileTabs />);

    await expect.element(component.getByRole("link", { name: "Profile" })).toBeVisible();
    await expect.element(component.getByRole("link", { name: "Tokens" })).toBeVisible();
    await expect.element(component.getByRole("link", { name: "Password" })).toBeVisible();
    expect(component.getByRole("link", { name: "Preferences" }).elements()).toHaveLength(0);
  });

  test("hides the Organisation defaults tab when the user cannot edit global preferences", async () => {
    mockCanEdit(false);

    const component = await render(<ProfileTabs />);

    expect(component.getByRole("link", { name: "Organisation defaults" }).elements()).toHaveLength(
      0
    );
  });

  test("shows the Organisation defaults tab when the user can edit global preferences", async () => {
    mockCanEdit(true);

    const component = await render(<ProfileTabs />);

    await expect
      .element(component.getByRole("link", { name: "Organisation defaults" }))
      .toBeVisible();
  });
});
