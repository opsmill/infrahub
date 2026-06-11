import { beforeEach, describe, expect, test, vi } from "vitest";

import { getGlobalPreference } from "@/entities/preferences/domain/get-global-preference";
import { getMyUserPreference } from "@/entities/preferences/domain/get-my-user-preference";
import { resetMyUserPreference } from "@/entities/preferences/domain/reset-my-user-preference";
import { upsertMyUserPreference } from "@/entities/preferences/domain/upsert-my-user-preference";

import { render } from "../../../../tests/components/render";
import TabPreferences from "./tab-preferences";

vi.mock("@/entities/preferences/domain/get-global-preference");
vi.mock("@/entities/preferences/domain/get-my-user-preference");
vi.mock("@/entities/preferences/domain/upsert-my-user-preference");
vi.mock("@/entities/preferences/domain/reset-my-user-preference");
vi.mock("@/entities/authentication/ui/useAuth", () => ({
  useAuth: () => ({
    accessToken: "",
    isAuthenticated: true,
    setToken: () => {},
    user: { id: "account-1" },
  }),
}));

describe("TabPreferences", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getGlobalPreference).mockResolvedValue({
      id: "global-1",
      dateFormat: "dd/MM/yyyy",
      timezone: "Europe/Paris",
    });
    vi.mocked(getMyUserPreference).mockResolvedValue(null);
    vi.mocked(upsertMyUserPreference).mockResolvedValue();
    vi.mocked(resetMyUserPreference).mockResolvedValue();
  });

  test("renders preset selects, not free-text inputs", async () => {
    const component = await render(<TabPreferences />);

    await expect.element(component.getByRole("button", { name: /date format/i })).toBeVisible();
    await expect.element(component.getByRole("combobox", { name: /timezone/i })).toBeVisible();
    expect(component.getByRole("textbox").elements()).toHaveLength(0);
  });

  test("shows the inherited global value as hint when the user has no override", async () => {
    const component = await render(<TabPreferences />);

    await expect
      .element(component.getByText(/inherited from organisation defaults:.*dd\/MM\/yyyy/i))
      .toBeVisible();
    await expect
      .element(component.getByText(/inherited from organisation defaults: Europe\/Paris/i))
      .toBeVisible();
  });

  test("saving triggers the lazy upsert with the selected values", async () => {
    const component = await render(<TabPreferences />);

    await component.getByRole("button", { name: /date format/i }).click();
    await component.getByRole("option", { name: /relative/i }).click();
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(upsertMyUserPreference).toHaveBeenCalledWith({
        accountId: "account-1",
        dateFormat: "relative",
        timezone: null,
      });
    });
  });

  test("reset to global deletes the override row when one exists", async () => {
    vi.mocked(getMyUserPreference).mockResolvedValue({
      id: "user-pref-1",
      dateFormat: "relative",
      timezone: null,
    });

    const component = await render(<TabPreferences />);

    await component.getByRole("button", { name: /reset to global/i }).click();

    await vi.waitFor(() => {
      expect(vi.mocked(resetMyUserPreference).mock.calls[0]?.[0]).toEqual({ id: "user-pref-1" });
    });
  });
});
