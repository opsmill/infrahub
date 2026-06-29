import { beforeEach, describe, expect, test, vi } from "vitest";

import { getEffectivePreferences } from "@/entities/preferences/domain/get-effective-preferences";
import type { EffectivePreferences } from "@/entities/preferences/domain/types";
import { updateGlobalPreference } from "@/entities/preferences/domain/update-global-preference";

import { render } from "../../../../tests/components/render";
import TabOrganisationDefaults from "./tab-organisation-defaults";

vi.mock("@/entities/preferences/domain/get-effective-preferences");
vi.mock("@/entities/preferences/domain/update-global-preference");

const baseEffective: EffectivePreferences = {
  dateFormat: "Europe/Paris",
  timezone: "Europe/Paris",
  userDateFormat: null,
  userTimezone: null,
  globalDateFormat: null,
  globalTimezone: "Europe/Paris",
  canEditGlobalPreferences: true,
};

describe("TabOrganisationDefaults", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getEffectivePreferences).mockResolvedValue(baseEffective);
    vi.mocked(updateGlobalPreference).mockResolvedValue();
  });

  test("shows an unauthorized screen when the user cannot edit global preferences", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      canEditGlobalPreferences: false,
    });

    const component = await render(<TabOrganisationDefaults />);

    await expect.element(component.getByText("You can't access this view")).toBeVisible();
    expect(component.getByRole("button", { name: "Save" }).elements()).toHaveLength(0);
  });

  test("edits the raw global_* values via the global mutation when allowed", async () => {
    const component = await render(<TabOrganisationDefaults />);

    await component.getByRole("button", { name: /date format/i }).click();
    await component.getByRole("option", { name: /relative/i }).click();
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(vi.mocked(updateGlobalPreference).mock.calls[0]?.[0]).toEqual({
        dateFormat: "relative",
        timezone: "Europe/Paris",
      });
    });
  });
});
