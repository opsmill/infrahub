import { beforeEach, describe, expect, test, vi } from "vitest";

import type { Permission } from "@/entities/permission/types";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";

import { render } from "../../../../tests/components/render";
import { ProfileTabs } from "./profile-tabs";

vi.mock("@/entities/permission/ui/queries/get-object-permissions.query", () => ({
  useGetObjectPermissions: vi.fn(),
}));

const allowed = { isAllowed: true } as const;
const denied = { isAllowed: false, message: "denied" } as const;

function mockPermissions(update: Permission["update"]) {
  vi.mocked(useGetObjectPermissions).mockReturnValue({
    isPending: false,
    error: null,
    data: { view: allowed, create: allowed, update, delete: allowed },
  } as ReturnType<typeof useGetObjectPermissions>);
}

describe("ProfileTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("hides the Organisation defaults tab without update permission on CoreGlobalPreference", async () => {
    mockPermissions(denied);

    const component = await render(<ProfileTabs />);

    await expect.element(component.getByRole("link", { name: "Preferences" })).toBeVisible();
    expect(component.getByRole("link", { name: "Organisation defaults" }).elements()).toHaveLength(
      0
    );
  });

  test("shows the Organisation defaults tab with update permission on CoreGlobalPreference", async () => {
    mockPermissions(allowed);

    const component = await render(<ProfileTabs />);

    await expect
      .element(component.getByRole("link", { name: "Organisation defaults" }))
      .toBeVisible();
    expect(useGetObjectPermissions).toHaveBeenCalledWith("CoreGlobalPreference");
  });
});
