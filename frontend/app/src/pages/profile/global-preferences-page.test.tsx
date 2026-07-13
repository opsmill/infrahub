import { beforeEach, describe, expect, test, vi } from "vitest";

import { MANAGE_GLOBAL_PREFERENCES } from "@/entities/permission/domain/model/permission";
import { hasGlobalPermission } from "@/entities/permission/domain/use-cases/has-global-permission";

import { render } from "../../../tests/components/render";
import { Component } from "./global-preferences-page";

vi.mock("@/entities/permission/domain/use-cases/has-global-permission");
vi.mock("@/entities/preferences/ui/global-preferences-editor", () => ({
  GlobalPreferencesEditor: () => <div data-testid="global-preferences-editor">editor</div>,
}));

describe("GlobalPreferencesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders the editor when the user can manage global preferences", async () => {
    vi.mocked(hasGlobalPermission).mockResolvedValue(true);

    const component = await render(<Component />);

    await expect.element(component.getByTestId("global-preferences-editor")).toBeVisible();
  });

  test("shows an unauthorized screen when the user cannot manage global preferences", async () => {
    vi.mocked(hasGlobalPermission).mockResolvedValue(false);

    const component = await render(<Component />);

    await expect.element(component.getByText("You can't access this view")).toBeVisible();
    expect(component.getByTestId("global-preferences-editor").elements()).toHaveLength(0);
  });

  test("gates on the manage_global_preferences permission action", async () => {
    vi.mocked(hasGlobalPermission).mockResolvedValue(true);

    await render(<Component />);

    await vi.waitFor(() => {
      expect(hasGlobalPermission).toHaveBeenCalledWith(MANAGE_GLOBAL_PREFERENCES);
    });
  });
});
