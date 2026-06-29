import { beforeEach, describe, expect, test, vi } from "vitest";

import { getEffectivePreferences } from "@/entities/preferences/domain/get-effective-preferences";
import type { EffectivePreferences } from "@/entities/preferences/domain/types";
import { upsertMyUserPreference } from "@/entities/preferences/domain/upsert-my-user-preference";

import { render } from "../../../../tests/components/render";
import { selectOption } from "../../../../tests/components/utils";
import TabPreferences from "./tab-preferences";

vi.mock("@/entities/preferences/domain/get-effective-preferences");
vi.mock("@/entities/preferences/domain/upsert-my-user-preference");

const baseEffective: EffectivePreferences = {
  dateFormat: "dd/MM/yyyy",
  timezone: "Europe/Paris",
  userDateFormat: null,
  userTimezone: null,
  globalDateFormat: "dd/MM/yyyy",
  globalTimezone: "Europe/Paris",
  canEditGlobalPreferences: false,
};

describe("TabPreferences", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getEffectivePreferences).mockResolvedValue(baseEffective);
    vi.mocked(upsertMyUserPreference).mockResolvedValue();
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

  test("pre-fills the form from the caller's own override", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      userDateFormat: "relative",
      userTimezone: "UTC",
    });

    const component = await render(<TabPreferences />);

    // The user's own override is shown, not the inherited hint.
    await expect
      .element(component.getByRole("combobox", { name: /timezone/i }))
      .toHaveTextContent("UTC");
    expect(component.getByText(/inherited from organisation defaults/i).elements()).toHaveLength(0);
  });

  test("still renders and saves the form when the effective query resolves with no global values", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: null,
      timezone: null,
      globalDateFormat: null,
      globalTimezone: null,
    });

    const component = await render(<TabPreferences />);

    await expect.element(component.getByRole("button", { name: "Save" })).toBeVisible();
    expect(
      component.getByText(/something went wrong when fetching your preferences/i).elements()
    ).toHaveLength(0);

    await selectOption(component, "Relative (2 days ago)");
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(upsertMyUserPreference).toHaveBeenCalledWith({
        dateFormat: "relative",
        timezone: null,
      });
    });
  });

  test("disables Save while the form is pristine", async () => {
    const component = await render(<TabPreferences />);

    await expect.element(component.getByRole("button", { name: "Save" })).toBeDisabled();

    await selectOption(component, "Relative (2 days ago)");

    await expect.element(component.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  test("saving triggers the upsert with the selected values", async () => {
    const component = await render(<TabPreferences />);

    await selectOption(component, "Relative (2 days ago)");
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(upsertMyUserPreference).toHaveBeenCalledWith({
        dateFormat: "relative",
        timezone: null,
      });
    });
  });

  test("reset to global sends an explicit-null upsert when the user has an override", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      userDateFormat: "relative",
      userTimezone: null,
    });

    const component = await render(<TabPreferences />);

    await component.getByRole("button", { name: /reset to global/i }).click();

    await vi.waitFor(() => {
      expect(vi.mocked(upsertMyUserPreference).mock.calls[0]?.[0]).toEqual({
        dateFormat: null,
        timezone: null,
      });
    });
  });

  test("hides the reset button when the user has no override", async () => {
    const component = await render(<TabPreferences />);

    await expect.element(component.getByRole("button", { name: "Save" })).toBeVisible();
    expect(component.getByRole("button", { name: /reset to global/i }).elements()).toHaveLength(0);
  });
});
