import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { getEffectivePreferences } from "@/entities/preferences/domain/get-effective-preferences";
import type { EffectivePreferences } from "@/entities/preferences/domain/types";
import { updateGlobalPreference } from "@/entities/preferences/domain/update-global-preference";

import { render } from "../../../../tests/components/render";
import { selectComboboxOption } from "../../../../tests/components/utils";
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
    // Date-format preset labels embed a live date example; freeze the clock.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-06-30T14:30:00"));
    vi.clearAllMocks();
    vi.mocked(getEffectivePreferences).mockResolvedValue(baseEffective);
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

    // Select by the stable preset key, not the (date-dependent) label.
    await selectComboboxOption(component, /date format/i, "relative");
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(vi.mocked(updateGlobalPreference).mock.calls[0]?.[0]).toEqual({
        dateFormat: "relative",
        timezone: "Europe/Paris",
      });
    });
  });
});
