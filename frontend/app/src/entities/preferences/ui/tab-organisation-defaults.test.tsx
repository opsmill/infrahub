import { beforeEach, describe, expect, test, vi } from "vitest";

import type { Permission } from "@/entities/permission/types";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { getGlobalPreference } from "@/entities/preferences/domain/get-global-preference";
import { updateGlobalPreference } from "@/entities/preferences/domain/update-global-preference";

import { render } from "../../../../tests/components/render";
import TabOrganisationDefaults from "./tab-organisation-defaults";

vi.mock("@/entities/permission/ui/queries/get-object-permissions.query", () => ({
  useGetObjectPermissions: vi.fn(),
}));
vi.mock("@/entities/preferences/domain/get-global-preference");
vi.mock("@/entities/preferences/domain/update-global-preference");

const allowed = { isAllowed: true } as const;

function mockPermissions(update: Permission["update"]) {
  vi.mocked(useGetObjectPermissions).mockReturnValue({
    isPending: false,
    error: null,
    data: { view: allowed, create: allowed, update, delete: allowed },
  } as ReturnType<typeof useGetObjectPermissions>);
}

describe("TabOrganisationDefaults", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getGlobalPreference).mockResolvedValue({
      id: "global-1",
      dateFormat: null,
      timezone: "Europe/Paris",
    });
    vi.mocked(updateGlobalPreference).mockResolvedValue();
  });

  test("shows an unauthorized screen without update permission", async () => {
    mockPermissions({ isAllowed: false, message: "denied" });

    const component = await render(<TabOrganisationDefaults />);

    await expect.element(component.getByText("You can't access this view")).toBeVisible();
    expect(component.getByRole("button", { name: "Save" }).elements()).toHaveLength(0);
  });

  test("edits the singleton global preference when allowed", async () => {
    mockPermissions(allowed);

    const component = await render(<TabOrganisationDefaults />);

    await component.getByRole("button", { name: /date format/i }).click();
    await component.getByRole("option", { name: /relative/i }).click();
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(vi.mocked(updateGlobalPreference).mock.calls[0]?.[0]).toEqual({
        id: "global-1",
        dateFormat: "relative",
        timezone: "Europe/Paris",
      });
    });
  });
});
