import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { getEffectivePreferences } from "@/entities/preferences/domain/get-effective-preferences";
import type { EffectivePreferences } from "@/entities/preferences/domain/types";
import { upsertMyUserPreference } from "@/entities/preferences/domain/upsert-my-user-preference";

import { render } from "../../../../tests/components/render";
import { selectComboboxOption } from "../../../../tests/components/utils";
import { UserPreferencesCard } from "./user-preferences-card";

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

describe("UserPreferencesCard", () => {
  beforeEach(() => {
    // The date-format preset labels embed a live example of the current date, so
    // freeze the clock to keep the rendered labels deterministic.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-06-30T14:30:00"));
    vi.clearAllMocks();
    vi.mocked(getEffectivePreferences).mockResolvedValue(baseEffective);
    vi.mocked(upsertMyUserPreference).mockResolvedValue();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("renders preset selects, not free-text inputs", async () => {
    const component = await render(<UserPreferencesCard />);

    // Both dropdowns are the shared Combobox now, so both expose role="combobox".
    await expect.element(component.getByRole("combobox", { name: /date format/i })).toBeVisible();
    await expect.element(component.getByRole("combobox", { name: /timezone/i })).toBeVisible();
    expect(component.getByRole("textbox").elements()).toHaveLength(0);
  });

  test("uses the preferences card title", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByText("Preferences")).toBeVisible();
  });

  test("lays the fields out as detail rows with a visible label and an accessible control", async () => {
    const component = await render(<UserPreferencesCard />);

    // The controls keep their accessible names even though their own labels are sr-only.
    await expect.element(component.getByRole("combobox", { name: /date format/i })).toBeVisible();
    await expect.element(component.getByRole("combobox", { name: /timezone/i })).toBeVisible();

    // The DetailRow term cells carry the visible field labels next to a leading icon,
    // in the object-details grid layout (a <dt> term + <dd> value).
    const terms = Array.from(component.container.querySelectorAll("dt")).map((dt) =>
      dt.textContent?.trim()
    );
    expect(terms).toContain("Date format");
    expect(terms).toContain("Timezone");
    expect(component.container.querySelectorAll("dt").length).toBeGreaterThanOrEqual(2);
    expect(component.container.querySelectorAll("dt iconify-icon").length).toBeGreaterThanOrEqual(
      2
    );
  });

  test("renders the row and action separators full-bleed (no horizontal inset)", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("combobox", { name: /date format/i })).toBeVisible();

    // Mirrors object-data-display: a single `divide-y divide-gray-200` container
    // with NO horizontal padding, so the divider lines reach both card edges.
    const divider = component.container.querySelector("div.divide-y.divide-gray-200");
    expect(divider).not.toBeNull();
    const dividerClasses = divider?.className ?? "";
    expect(dividerClasses).not.toMatch(/(^|\s)px-/);
    expect(dividerClasses).not.toMatch(/(^|\s)pl-/);
    expect(dividerClasses).not.toMatch(/(^|\s)pr-/);

    // The field rows carry their own px-3 (so the values are inset, the lines are not).
    const rows = divider ? Array.from(divider.children) : [];
    expect(rows.length).toBeGreaterThanOrEqual(2);
    for (const row of rows) {
      expect(row.className).toMatch(/(^|\s)px-3(\s|$)/);
    }

    // The Save button lives in the last child of the same divide container, so it
    // sits under a full-width line.
    const actionRow = rows.at(-1) as HTMLElement;
    expect(actionRow.querySelector("button")).not.toBeNull();
  });

  test("shows the inherited global value as hint when the user has no override", async () => {
    const component = await render(<UserPreferencesCard />);

    // globalDateFormat is "dd/MM/yyyy"; the hint shows a live example of the
    // frozen current date rendered with that pattern, then the pattern.
    await expect
      .element(
        component.getByText(/inherited from organisation defaults: 30\/06\/2026 \(dd\/MM\/yyyy\)/i)
      )
      .toBeVisible();
    await expect
      .element(component.getByText(/inherited from organisation defaults: Europe\/Paris/i))
      .toBeVisible();
  });

  test("falls back to the browser default hint when neither user nor global is set", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: null,
      timezone: null,
      globalDateFormat: null,
      globalTimezone: null,
    });

    const component = await render(<UserPreferencesCard />);

    // No fixed "yyyy-MM-dd HH:mm (built-in default)" any more: the effective default
    // is the browser's own locale/timezone. The date hint shows a concrete
    // browser-formatted example of the frozen current date.
    const expectedDateExample = new Date("2026-06-30T14:30:00").toLocaleString();
    const expectedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

    await expect
      .element(component.getByText(`Browser default: ${expectedDateExample}`))
      .toBeVisible();
    await expect.element(component.getByText(`Browser default: ${expectedTimezone}`)).toBeVisible();
    expect(component.getByText(/built-in default/i).elements()).toHaveLength(0);
  });

  test("date-format options are labelled by the pattern itself", async () => {
    const component = await render(<UserPreferencesCard />);

    // Open the date-format Combobox; its options are cmdk role="option" entries.
    await component.getByRole("combobox", { name: /date format/i }).click();

    // The option label is the pattern/sentinel itself, not a live example. The
    // "yyyy-MM-dd HH:mm" pattern remains a selectable preset (just not THE default).
    await expect.element(component.getByRole("option", { name: "yyyy-MM-dd HH:mm" })).toBeVisible();
    await expect.element(component.getByRole("option", { name: "relative" })).toBeVisible();
  });

  test("shows a live example next to the date-format control that updates on selection", async () => {
    const component = await render(<UserPreferencesCard />);

    // No personal override yet, so no example is shown until a format is picked.
    expect(component.getByText(/^Example:/i).elements()).toHaveLength(0);

    // Frozen at 2026-06-30T14:30:00; the ISO preset renders that instant.
    await selectComboboxOption(component, /date format/i, "yyyy-MM-dd HH:mm");
    await expect.element(component.getByText("Example: 2026-06-30 14:30")).toBeVisible();

    // Switching the selection updates the example deterministically.
    await selectComboboxOption(component, /date format/i, "relative");
    await expect.element(component.getByText("Example: 2 days ago")).toBeVisible();
  });

  test("pre-fills the form from the caller's own override", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      userDateFormat: "relative",
      userTimezone: "UTC",
    });

    const component = await render(<UserPreferencesCard />);

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

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: "Save" })).toBeVisible();
    expect(
      component.getByText(/something went wrong when fetching your preferences/i).elements()
    ).toHaveLength(0);

    // Select by the stable preset key, not the (date-dependent) label.
    await selectComboboxOption(component, /date format/i, "relative");
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(upsertMyUserPreference).toHaveBeenCalledWith({
        dateFormat: "relative",
        timezone: null,
      });
    });
  });

  test("disables Save while the form is pristine", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: "Save" })).toBeDisabled();

    // Select by the stable preset key, not the (date-dependent) label.
    await selectComboboxOption(component, /date format/i, "relative");

    await expect.element(component.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  test("saving triggers the upsert with the selected values", async () => {
    const component = await render(<UserPreferencesCard />);

    // Select by the stable preset key, not the (date-dependent) label.
    await selectComboboxOption(component, /date format/i, "relative");
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

    const component = await render(<UserPreferencesCard />);

    await component.getByRole("button", { name: /reset to global/i }).click();

    await vi.waitFor(() => {
      expect(vi.mocked(upsertMyUserPreference).mock.calls[0]?.[0]).toEqual({
        dateFormat: null,
        timezone: null,
      });
    });
  });

  test("hides the reset button when the user has no override", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: "Save" })).toBeVisible();
    expect(component.getByRole("button", { name: /reset to global/i }).elements()).toHaveLength(0);
  });
});
