import type { UseQueryResult } from "@tanstack/react-query";
import { beforeEach, describe, expect, test, vi } from "vitest";

import type { EffectivePreferences } from "@/entities/preferences/domain/types";
import { useEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";

import { render } from "../../../../tests/components/render";
import { ProfileTabs } from "./profile-tabs";

vi.mock("@/entities/preferences/ui/queries/get-effective-preferences.query", () => ({
  useEffectivePreferences: vi.fn(),
}));

function mockCanEdit(canEditGlobalPreferences: boolean) {
  vi.mocked(useEffectivePreferences).mockReturnValue({
    isPending: false,
    error: null,
    data: { canEditGlobalPreferences } as EffectivePreferences,
  } as UseQueryResult<EffectivePreferences>);
}

describe("ProfileTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("hides the Organisation defaults tab when the user cannot edit global preferences", async () => {
    mockCanEdit(false);

    const component = await render(<ProfileTabs />);

    await expect.element(component.getByRole("link", { name: "Preferences" })).toBeVisible();
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
