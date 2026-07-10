import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { EffectivePreferences } from "@/entities/preferences/domain/model/preference";
import { getEffectivePreferences } from "@/entities/preferences/domain/use-cases/get-effective-preferences";
import { upsertMyUserPreference } from "@/entities/preferences/domain/use-cases/upsert-my-user-preference";

import { render } from "../../../../tests/components/render";
import { initPointerTracking, selectComboboxOption } from "../../../../tests/components/utils";
import { UserPreferencesCard } from "./user-preferences-card";

vi.mock("@/entities/preferences/domain/use-cases/get-effective-preferences");
vi.mock("@/entities/preferences/domain/use-cases/upsert-my-user-preference");

const baseEffective: EffectivePreferences = {
  // No personal override → both fields resolve to the org default (source "global").
  // date_format is a semantic key (see DateFormatKey), not a pattern.
  dateFormat: { value: "EU_DATETIME", source: "GLOBAL" },
  timezone: { value: "Europe/Paris", source: "GLOBAL" },
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

    // Both dropdowns are the shared Combobox, so both expose role="combobox".
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

    // DetailRow renders each field as a <dt> term (label + icon) + <dd> value.
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

    // The Save button is the last child of the divide container, so it sits under a full-width line.
    const actionRow = rows.at(-1) as HTMLElement;
    expect(actionRow.querySelector("button")).not.toBeNull();
  });

  test("shows the 'Automatic (inherited)' placeholder when the user has no override", async () => {
    const component = await render(<UserPreferencesCard />);

    // Both fields resolve to source "global" (no personal override), so each trigger shows the
    // inherit placeholder rather than a concrete value.
    await expect
      .element(component.getByRole("combobox", { name: /date format/i }))
      .toHaveTextContent("Automatic (inherited)");
    await expect
      .element(component.getByRole("combobox", { name: /timezone/i }))
      .toHaveTextContent("Automatic (inherited)");
  });

  test("date-format options are labelled by the pattern itself", async () => {
    const component = await render(<UserPreferencesCard />);

    // Open the date-format Combobox; its options are cmdk role="option" entries.
    await component.getByRole("combobox", { name: /date format/i }).click();

    // The option label is the human-facing pattern text, not a live example. The stored value is
    // the semantic key behind the label.
    // exact: true — otherwise "yyyy-MM-dd HH:mm" also matches the "yyyy-MM-dd HH:mm:ss" preset.
    await expect
      .element(component.getByRole("option", { name: "yyyy-MM-dd HH:mm", exact: true }))
      .toBeVisible();
    await expect.element(component.getByRole("option", { name: "dd/MM/yyyy HH:mm" })).toBeVisible();
  });

  test("shows a live example next to the date-format control that updates on selection", async () => {
    const component = await render(<UserPreferencesCard />);

    // No override is set, so no concrete example is shown until a real format is picked.
    expect(component.getByText(/^Example:/i).elements()).toHaveLength(0);

    // Frozen at 2026-06-30T14:30:00; the ISO preset renders that instant.
    await selectComboboxOption(component, /date format/i, "yyyy-MM-dd HH:mm");
    await expect.element(component.getByText("Example: 2026-06-30 14:30")).toBeVisible();

    // Switching the selection updates the example deterministically.
    await selectComboboxOption(component, /date format/i, "dd/MM/yyyy HH:mm");
    await expect.element(component.getByText("Example: 30/06/2026 14:30")).toBeVisible();
  });

  test("renders the live example inline, on the same row as the date-format control", async () => {
    const component = await render(<UserPreferencesCard />);

    await selectComboboxOption(component, /date format/i, "dd/MM/yyyy HH:mm");

    const combobox = component.getByRole("combobox", { name: /date format/i }).element();
    const example = component.getByText("Example: 30/06/2026 14:30").element();

    // The example and the combobox share the same horizontal row container
    // ([combobox] [example] [(i)]), rather than the example sitting on a row below.
    const row = combobox.closest("div.flex.items-center") as HTMLElement;
    expect(row).not.toBeNull();
    expect(row.contains(example)).toBe(true);

    // The example follows the control in document order (to its right).
    const children = Array.from(row.children);
    const controlIndex = children.findIndex((child) => child.contains(combobox));
    const exampleIndex = children.findIndex((child) => child.contains(example));
    expect(controlIndex).toBeGreaterThanOrEqual(0);
    expect(exampleIndex).toBeGreaterThan(controlIndex);
  });

  test("hides the example again when the override is cleared by re-selecting it", async () => {
    const component = await render(<UserPreferencesCard />);

    // Selecting a concrete format shows its example.
    await selectComboboxOption(component, /date format/i, "dd/MM/yyyy HH:mm");
    await expect.element(component.getByText("Example: 30/06/2026 14:30")).toBeVisible();

    // Re-selecting the currently-selected format clears the override (maps to null),
    // so the example disappears.
    await selectComboboxOption(component, /date format/i, "dd/MM/yyyy HH:mm");
    expect(component.getByText(/^Example:/i).elements()).toHaveLength(0);
  });

  test("pre-fills the form from the caller's own override", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: { value: "EU_DATETIME", source: "USER" },
      timezone: { value: "UTC", source: "USER" },
    });

    const component = await render(<UserPreferencesCard />);

    // The user's own override is shown, not the inherit placeholder.
    await expect
      .element(component.getByRole("combobox", { name: /timezone/i }))
      .toHaveTextContent("UTC");
    await expect
      .element(component.getByRole("combobox", { name: /date format/i }))
      .toHaveTextContent("dd/MM/yyyy HH:mm");
  });

  test("does not render the below-input source/inheritance sentence", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("combobox", { name: /date format/i })).toBeVisible();

    // Source is conveyed via the (i) tooltip, not a below-input sentence.
    expect(component.getByText(/inherited from organisation defaults/i).elements()).toHaveLength(0);
    expect(component.getByText(/browser default:/i).elements()).toHaveLength(0);
  });

  test("provides one accessible, focusable (i) source tooltip trigger per field", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("combobox", { name: /date format/i })).toBeVisible();

    // One info trigger per field, each a real keyboard-focusable <button> (not hover-only).
    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    expect(triggers.elements()).toHaveLength(2);
    for (const trigger of triggers.elements()) {
      expect(trigger.tagName).toBe("BUTTON");
    }
  });

  test("the (i) tooltip resolves to the organisation default when no override is set", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("combobox", { name: /date format/i })).toBeVisible();

    // No user override + global set → the date-format tooltip resolves to the org
    // default (a live example of the frozen date plus the inherited format's label).
    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.first().hover();

    await expect
      .element(
        component.getByRole("tooltip", {
          name: /from the organisation default: 30\/06\/2026 14:30 \(dd\/MM\/yyyy HH:mm\)/i,
        })
      )
      .toBeVisible();
  });

  test("the (i) tooltip reflects the user's own preference when an override is set", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: { value: "EU_DATETIME", source: "USER" },
      timezone: { value: "UTC", source: "USER" },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("combobox", { name: /date format/i })).toBeVisible();

    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.first().hover();

    await expect
      .element(component.getByRole("tooltip", { name: "Your preference." }))
      .toBeVisible();
  });

  test("the (i) tooltip falls back to the browser source when neither user nor global is set", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: { value: null, source: "DEFAULT" },
      timezone: { value: null, source: "DEFAULT" },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("combobox", { name: /timezone/i })).toBeVisible();

    const expectedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

    // The timezone field is the second info trigger.
    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.nth(1).hover();

    await expect
      .element(component.getByRole("tooltip", { name: `From your browser: ${expectedTimezone}.` }))
      .toBeVisible();
  });

  test("disables Save while the form is pristine", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: "Save" })).toBeDisabled();

    // Select by the stable preset key, not the (date-dependent) label.
    await selectComboboxOption(component, /date format/i, "dd/MM/yyyy HH:mm");

    await expect.element(component.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  test("saving triggers the upsert with the selected values", async () => {
    const component = await render(<UserPreferencesCard />);

    // Select by the stable preset key, not the (date-dependent) label.
    await selectComboboxOption(component, /date format/i, "dd/MM/yyyy HH:mm");
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(upsertMyUserPreference).toHaveBeenCalledWith({
        dateFormat: "EU_DATETIME",
        timezone: null,
      });
    });
  });

  test("re-selecting the current value clears the override with an explicit-null upsert", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: { value: "EU_DATETIME", source: "USER" },
      timezone: { value: "UTC", source: "USER" },
    });

    const component = await render(<UserPreferencesCard />);

    // Pre-filled from the override; re-selecting the currently-selected value resets to inherit.
    await expect
      .element(component.getByRole("combobox", { name: /date format/i }))
      .toHaveTextContent("dd/MM/yyyy HH:mm");

    await selectComboboxOption(component, /date format/i, "dd/MM/yyyy HH:mm");
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      // date_format cleared to null; timezone keeps the existing UTC override.
      expect(vi.mocked(upsertMyUserPreference).mock.calls[0]?.[0]).toEqual({
        dateFormat: null,
        timezone: "UTC",
      });
    });
  });

  test("no longer renders a separate 'reset to global' button", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: { value: "EU_DATETIME", source: "USER" },
      timezone: { value: "Europe/Paris", source: "GLOBAL" },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: "Save" })).toBeVisible();
    expect(component.getByRole("button", { name: /reset to global/i }).elements()).toHaveLength(0);
  });

  test("still renders and saves the form when the effective query resolves with no global values", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: { value: null, source: "DEFAULT" },
      timezone: { value: null, source: "DEFAULT" },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: "Save" })).toBeVisible();
    expect(
      component.getByText(/something went wrong when fetching your preferences/i).elements()
    ).toHaveLength(0);

    // Select by the stable preset key, not the (date-dependent) label.
    await selectComboboxOption(component, /date format/i, "dd/MM/yyyy HH:mm");
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(upsertMyUserPreference).toHaveBeenCalledWith({
        dateFormat: "EU_DATETIME",
        timezone: null,
      });
    });
  });
});
