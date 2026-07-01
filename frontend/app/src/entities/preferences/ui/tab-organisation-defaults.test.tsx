import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { getEffectivePreferences } from "@/entities/preferences/domain/get-effective-preferences";
import { getGlobalPreferences } from "@/entities/preferences/domain/get-global-preferences";
import type { EffectivePreferences, GlobalPreferences } from "@/entities/preferences/domain/types";
import { updateGlobalPreference } from "@/entities/preferences/domain/update-global-preference";

import { render } from "../../../../tests/components/render";
import { selectComboboxOption } from "../../../../tests/components/utils";
import TabOrganisationDefaults from "./tab-organisation-defaults";

vi.mock("@/entities/preferences/domain/get-effective-preferences");
vi.mock("@/entities/preferences/domain/get-global-preferences");
vi.mock("@/entities/preferences/domain/update-global-preference");

// The effective query only supplies the `can_edit_global_preferences` gate here;
// its resolved values are irrelevant to this tab (it edits the raw GLOBAL scope).
const baseEffective: EffectivePreferences = {
  dateFormat: { value: "EU_DATETIME", source: "global" },
  timezone: { value: "Europe/Paris", source: "global" },
  canEditGlobalPreferences: true,
};

// The raw organisation defaults (scope GLOBAL) the form prefills from.
const baseGlobal: GlobalPreferences = { dateFormat: null, timezone: "Europe/Paris" };

describe("TabOrganisationDefaults", () => {
  beforeEach(() => {
    // Date-format preset labels embed a live date example; freeze the clock.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-06-30T14:30:00"));
    vi.clearAllMocks();
    vi.mocked(getEffectivePreferences).mockResolvedValue(baseEffective);
    vi.mocked(getGlobalPreferences).mockResolvedValue(baseGlobal);
    vi.mocked(updateGlobalPreference).mockResolvedValue();
  });

  afterEach(() => {
    vi.useRealTimers();
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

  test("uses the global card title", async () => {
    const component = await render(<TabOrganisationDefaults />);

    await expect.element(component.getByText("Global date and time")).toBeVisible();
  });

  test("renders the card wide enough (max-w-3xl) for the inline date-format example", async () => {
    const component = await render(<TabOrganisationDefaults />);

    await expect.element(component.getByText("Global date and time")).toBeVisible();

    const title = component.getByText("Global date and time").element() as HTMLElement;
    // The card is the title's ancestor carrying the width cap; widened from
    // max-w-2xl to max-w-3xl so the longest inline example never clips.
    const card = title.closest(".max-w-3xl");
    expect(card).not.toBeNull();
    expect(card?.className).not.toMatch(/max-w-2xl/);
  });

  test("shows the live date-format example inline next to the control", async () => {
    const component = await render(<TabOrganisationDefaults />);

    // Frozen at 2026-06-30T14:30:00; selecting a concrete preset surfaces the example.
    await selectComboboxOption(component, /date format/i, "yyyy-MM-dd HH:mm");

    const combobox = component.getByRole("combobox", { name: /date format/i }).element();
    const example = component.getByText("Example: 2026-06-30 14:30").element();

    const row = combobox.closest("div.flex.items-center") as HTMLElement;
    expect(row).not.toBeNull();
    expect(row.contains(example)).toBe(true);
  });

  test("edits the raw global_* values via the global mutation when allowed", async () => {
    const component = await render(<TabOrganisationDefaults />);

    // Select an option by its visible label; the stored value is the semantic key behind it.
    await selectComboboxOption(component, /date format/i, "dd/MM/yyyy HH:mm");
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(vi.mocked(updateGlobalPreference).mock.calls[0]?.[0]).toEqual({
        dateFormat: "EU_DATETIME",
        timezone: "Europe/Paris",
      });
    });
  });

  test("prefills from the raw GLOBAL scope, not the admin's own personal override", async () => {
    // An admin who also set personal overrides: the effective query resolves those
    // overrides (source "user"), but the org-defaults form must show the organisation's
    // own values from the GLOBAL scope, never the admin's overrides.
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: { value: "EU_DATETIME", source: "user" },
      timezone: { value: "UTC", source: "user" },
    });
    vi.mocked(getGlobalPreferences).mockResolvedValue({
      dateFormat: "ISO_DATETIME",
      timezone: "Europe/Paris",
    });

    const component = await render(<TabOrganisationDefaults />);

    // The form prefills from the GLOBAL scope (the org default), not the user override.
    await expect
      .element(component.getByRole("combobox", { name: /date format/i }))
      .toHaveTextContent("yyyy-MM-dd HH:mm");
    await expect
      .element(component.getByRole("combobox", { name: /timezone/i }))
      .toHaveTextContent("Europe/Paris");
  });
});
