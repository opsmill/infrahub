import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { EffectivePreferences } from "@/entities/preferences/domain/model/preference";
import { getEffectivePreferences } from "@/entities/preferences/domain/use-cases/get-effective-preferences";
import { upsertUserPreferences } from "@/entities/preferences/domain/use-cases/upsert-user-preferences";

import { render } from "../../../../tests/components/render";
import { initPointerTracking } from "../../../../tests/components/utils";
import { UserPreferencesCard } from "./user-preferences-card";

vi.mock("@/entities/preferences/domain/use-cases/get-effective-preferences");
vi.mock("@/entities/preferences/domain/use-cases/upsert-user-preferences");

// Late-evening UTC: in the effective zone (UTC+9) this lands on the NEXT calendar day, so an example
// that ignored the timezone cannot match by accident. A zone-less literal would be browser-local.
const FIXED_INSTANT = new Date("2026-06-11T23:30:00Z");
const EFFECTIVE_ZONE = "Asia/Tokyo";

// A non-USER source inherits its own {value, source}; a USER source states the layer it shadows.
const baseEffective: EffectivePreferences = {
  dateFormat: {
    value: "EU_DATETIME",
    source: "GLOBAL",
    inherited: { value: "EU_DATETIME", source: "GLOBAL" },
  },
  timezone: {
    value: EFFECTIVE_ZONE,
    source: "GLOBAL",
    inherited: { value: EFFECTIVE_ZONE, source: "GLOBAL" },
  },
};

describe("UserPreferencesCard", () => {
  beforeEach(() => {
    // Freeze the clock: preset labels embed a live date example.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(FIXED_INSTANT);
    vi.clearAllMocks();
    vi.mocked(getEffectivePreferences).mockResolvedValue(baseEffective);
    vi.mocked(upsertUserPreferences).mockResolvedValue();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("renders preset selects, not free-text inputs", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /date format/i })).toBeVisible();
    await expect.element(component.getByRole("button", { name: /timezone/i })).toBeVisible();
    expect(component.getByRole("textbox").elements()).toHaveLength(0);
  });

  test("uses the preferences card title", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByText("Preferences")).toBeVisible();
  });

  test("lays the fields out as detail rows with a visible label and an accessible control", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /date format/i })).toBeVisible();
    await expect.element(component.getByRole("button", { name: /timezone/i })).toBeVisible();

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

  test("shows the 'Automatic (inherited)' placeholder when the user has no override", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect
      .element(component.getByRole("button", { name: /date format/i }))
      .toHaveTextContent("Automatic (inherited)");
    await expect
      .element(component.getByRole("button", { name: /timezone/i }))
      .toHaveTextContent("Automatic (inherited)");
  });

  test("date-format options are labelled by the pattern itself", async () => {
    const component = await render(<UserPreferencesCard />);

    await component.getByRole("button", { name: /date format/i }).click();

    // exact: true — otherwise "yyyy-MM-dd HH:mm" also matches the "yyyy-MM-dd HH:mm:ss" preset.
    await expect
      .element(component.getByRole("option", { name: "yyyy-MM-dd HH:mm", exact: true }))
      .toBeVisible();
    await expect.element(component.getByRole("option", { name: "dd/MM/yyyy HH:mm" })).toBeVisible();
  });

  test("shows a live example next to the date-format control that updates on selection", async () => {
    const component = await render(<UserPreferencesCard />);

    // Pristine, the preview already stands in for the inherited organisation format.
    await expect.element(component.getByText("Example: 12/06/2026 08:30")).toBeVisible();

    await component.getByRole("button", { name: /date format/i }).click();

    await component.getByRole("option", { name: "yyyy-MM-dd HH:mm", exact: true }).click();
    await expect.element(component.getByText("Example: 2026-06-12 08:30")).toBeVisible();

    await component.getByRole("button", { name: /date format/i }).click();

    await component.getByRole("option", { name: "dd/MM/yyyy HH:mm", exact: true }).click();
    await expect.element(component.getByText("Example: 12/06/2026 08:30")).toBeVisible();
  });

  test("renders the example in the effective timezone, not the browser's", async () => {
    const component = await render(<UserPreferencesCard />);

    await component.getByRole("button", { name: /date format/i }).click();
    await component.getByRole("option", { name: "yyyy-MM-dd HH:mm", exact: true }).click();

    // 23:30Z is 08:30 the next day in Asia/Tokyo; the browser-zone rendering would still say the 11th.
    await expect.element(component.getByText("Example: 2026-06-12 08:30")).toBeVisible();
    expect(component.getByText(/^Example: 2026-06-11/).elements()).toHaveLength(0);
  });

  test("renders the example's offset from the effective timezone, not the browser's", async () => {
    const component = await render(<UserPreferencesCard />);

    await component.getByRole("button", { name: /date format/i }).click();
    await component.getByRole("option", { name: "yyyy-MM-dd'T'HH:mm:ssXXX", exact: true }).click();

    await expect.element(component.getByText("Example: 2026-06-12T08:30:00+09:00")).toBeVisible();
  });

  test("renders the live example inline, on the same row as the date-format control", async () => {
    const component = await render(<UserPreferencesCard />);

    await component.getByRole("button", { name: /date format/i }).click();

    await component.getByRole("option", { name: "dd/MM/yyyy HH:mm", exact: true }).click();

    const combobox = component.getByRole("button", { name: /date format/i }).element();
    const example = component.getByText("Example: 12/06/2026 08:30").element();

    const row = combobox.closest("div.flex.items-center") as HTMLElement;
    expect(row).not.toBeNull();
    expect(row.contains(example)).toBe(true);

    const children = Array.from(row.children);
    const controlIndex = children.findIndex((child) => child.contains(combobox));
    const exampleIndex = children.findIndex((child) => child.contains(example));
    expect(controlIndex).toBeGreaterThanOrEqual(0);
    expect(exampleIndex).toBeGreaterThan(controlIndex);
  });

  test("returns the example to the inherited format when the override is cleared", async () => {
    const component = await render(<UserPreferencesCard />);

    await component.getByRole("button", { name: /date format/i }).click();

    await component.getByRole("option", { name: "yyyy-MM-dd HH:mm", exact: true }).click();
    await expect.element(component.getByText("Example: 2026-06-12 08:30")).toBeVisible();

    // Re-selecting the already-selected format clears the override.
    await component.getByRole("button", { name: /date format/i }).click();

    await component.getByRole("option", { name: "yyyy-MM-dd HH:mm", exact: true }).click();
    // The inherited organisation format, not a blank row: the preview previews what saving produces.
    await expect.element(component.getByText("Example: 12/06/2026 08:30")).toBeVisible();
  });

  test("returns the example to the inherited format when a saved override is cleared", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: {
        value: "ISO_DATETIME",
        source: "USER",
        inherited: { value: "EU_DATETIME", source: "GLOBAL" },
      },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByText("Example: 2026-06-12 08:30")).toBeVisible();

    await component.getByRole("button", { name: /date format/i }).click();
    await component.getByRole("option", { name: "yyyy-MM-dd HH:mm", exact: true }).click();

    await expect.element(component.getByText("Example: 12/06/2026 08:30")).toBeVisible();
  });

  test("switches the date-format (i) tooltip to the organisation default when the field is cleared", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: {
        value: "ISO_DATETIME",
        source: "USER",
        inherited: { value: "EU_DATETIME", source: "GLOBAL" },
      },
    });

    const component = await render(<UserPreferencesCard />);

    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.first().hover();

    await expect
      .element(
        component.getByRole("tooltip", {
          name: "Your preference, overriding the organisation default: dd/MM/yyyy HH:mm.",
        })
      )
      .toBeVisible();

    await initPointerTracking(component.locator);

    await component.getByRole("button", { name: /date format/i }).click();
    await component.getByRole("option", { name: "yyyy-MM-dd HH:mm", exact: true }).click();

    await initPointerTracking(component.locator);
    await triggers.first().hover();

    // Nothing has been saved, so only the pending state can explain the row the user is looking at.
    await expect
      .element(
        component.getByRole("tooltip", {
          name: "From the organisation default: dd/MM/yyyy HH:mm.",
        })
      )
      .toBeVisible();

    await initPointerTracking(component.locator);
  });

  test("pre-fills the form from the caller's own override", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: {
        value: "EU_DATETIME",
        source: "USER",
        inherited: { value: null, source: "DEFAULT" },
      },
      timezone: { value: "UTC", source: "USER", inherited: { value: null, source: "DEFAULT" } },
    });

    const component = await render(<UserPreferencesCard />);

    await expect
      .element(component.getByRole("button", { name: /timezone/i }))
      .toHaveTextContent("UTC");
    await expect
      .element(component.getByRole("button", { name: /date format/i }))
      .toHaveTextContent("dd/MM/yyyy HH:mm");
  });

  test("does not render the below-input source/inheritance sentence", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /date format/i })).toBeVisible();

    expect(component.getByText(/inherited from organisation defaults/i).elements()).toHaveLength(0);
    expect(component.getByText(/browser default:/i).elements()).toHaveLength(0);
  });

  test("provides one accessible, focusable (i) source tooltip trigger per field", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /date format/i })).toBeVisible();

    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    expect(triggers.elements()).toHaveLength(2);
    for (const trigger of triggers.elements()) {
      expect(trigger.tagName).toBe("BUTTON");
    }
  });

  test("the (i) tooltip resolves to the organisation default when no override is set", async () => {
    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /date format/i })).toBeVisible();

    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.first().hover();

    // Provenance only: the format is named by its label, never by a rendered date sample.
    await expect
      .element(
        component.getByRole("tooltip", { name: "From the organisation default: dd/MM/yyyy HH:mm." })
      )
      .toBeVisible();

    await initPointerTracking(component.locator);
  });

  test("the (i) tooltip names the organisation default a user override is shadowing", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: {
        value: "EU_DATETIME",
        source: "USER",
        inherited: { value: "ISO_DATETIME", source: "GLOBAL" },
      },
      timezone: { value: "UTC", source: "USER", inherited: { value: null, source: "DEFAULT" } },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /date format/i })).toBeVisible();

    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.first().hover();

    await expect
      .element(
        component.getByRole("tooltip", {
          name: "Your preference, overriding the organisation default: yyyy-MM-dd HH:mm.",
        })
      )
      .toBeVisible();

    await initPointerTracking(component.locator);
  });

  test("the (i) tooltip stays a bare 'Your preference.' when the override shadows nothing", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: {
        value: "EU_DATETIME",
        source: "USER",
        inherited: { value: null, source: "DEFAULT" },
      },
      timezone: { value: "UTC", source: "USER", inherited: { value: null, source: "DEFAULT" } },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /date format/i })).toBeVisible();

    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.first().hover();

    // No organisation default to name, so no empty clause is appended.
    await expect
      .element(component.getByRole("tooltip", { name: "Your preference." }))
      .toBeVisible();

    await initPointerTracking(component.locator);
  });

  test("the (i) tooltip drops the overriding clause when the override matches the organisation default", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: {
        value: "EU_DATETIME",
        source: "USER",
        inherited: { value: "EU_DATETIME", source: "GLOBAL" },
      },
      timezone: {
        value: EFFECTIVE_ZONE,
        source: "USER",
        inherited: { value: EFFECTIVE_ZONE, source: "GLOBAL" },
      },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /date format/i })).toBeVisible();

    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.first().hover();

    await expect
      .element(component.getByRole("tooltip", { name: "Your preference." }))
      .toBeVisible();

    await initPointerTracking(component.locator);

    // The timezone field is the second info trigger.
    await initPointerTracking(component.locator);
    await triggers.nth(1).hover();

    await expect
      .element(component.getByRole("tooltip", { name: "Your preference." }))
      .toBeVisible();

    await initPointerTracking(component.locator);
  });

  test("the date-format (i) tooltip names only the source, with no rendered date sample", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: { value: null, source: "DEFAULT", inherited: { value: null, source: "DEFAULT" } },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /date format/i })).toBeVisible();

    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.first().hover();

    // Provenance only: the source is named, never illustrated with a rendered date sample.
    await expect
      .element(component.getByRole("tooltip", { name: "From your browser." }))
      .toBeVisible();

    const tooltip = component.getByRole("tooltip").element();
    expect(tooltip.textContent).not.toMatch(/2026/);
    expect(tooltip.textContent).not.toMatch(/Asia\/Tokyo/);

    await initPointerTracking(component.locator);
  });

  test("the timezone (i) tooltip names the organisation zone a user override is shadowing", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      timezone: {
        value: "America/New_York",
        source: "USER",
        inherited: { value: EFFECTIVE_ZONE, source: "GLOBAL" },
      },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /timezone/i })).toBeVisible();

    // The timezone field is the second info trigger.
    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.nth(1).hover();

    // A renderable stored zone falls through the supportedTimezone pre-check to the shared
    // provenance message, which names the layer the override is hiding.
    await expect
      .element(
        component.getByRole("tooltip", {
          name: `Your preference, overriding the organisation default: ${EFFECTIVE_ZONE}.`,
        })
      )
      .toBeVisible();

    await initPointerTracking(component.locator);
  });

  test("the timezone (i) tooltip stays a bare 'Your preference.' when the override shadows nothing", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      timezone: { value: "UTC", source: "USER", inherited: { value: null, source: "DEFAULT" } },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /timezone/i })).toBeVisible();

    // The timezone field is the second info trigger.
    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.nth(1).hover();

    // No organisation default to name, so no empty clause is appended — and no browser zone either,
    // since the caller's own override is what is in effect.
    await expect
      .element(component.getByRole("tooltip", { name: "Your preference." }))
      .toBeVisible();

    await initPointerTracking(component.locator);
  });

  test("the (i) tooltip reports the browser fallback when the stored zone can't be rendered here", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      timezone: {
        value: "Not/AZone",
        source: "USER",
        inherited: { value: null, source: "DEFAULT" },
      },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /timezone/i })).toBeVisible();

    const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

    // The timezone field is the second info trigger.
    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.nth(1).hover();

    await expect
      .element(
        component.getByRole("tooltip", {
          name: `This browser can't display Not/AZone; times are shown in ${browserZone}.`,
        })
      )
      .toBeVisible();

    await initPointerTracking(component.locator);
  });

  test("the (i) tooltip reports the browser fallback for an unrenderable organisation-default zone", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      timezone: {
        value: "Not/AZone",
        source: "GLOBAL",
        inherited: { value: "Not/AZone", source: "GLOBAL" },
      },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /timezone/i })).toBeVisible();

    const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

    // The timezone field is the second info trigger.
    const triggers = component.getByRole("button", { name: "Where this value comes from" });
    await initPointerTracking(component.locator);
    await triggers.nth(1).hover();

    await expect
      .element(
        component.getByRole("tooltip", {
          name: `This browser can't display Not/AZone; times are shown in ${browserZone}.`,
        })
      )
      .toBeVisible();

    await initPointerTracking(component.locator);
  });

  test("the (i) tooltip falls back to the browser source when neither user nor global is set", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: { value: null, source: "DEFAULT", inherited: { value: null, source: "DEFAULT" } },
      timezone: { value: null, source: "DEFAULT", inherited: { value: null, source: "DEFAULT" } },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: /timezone/i })).toBeVisible();

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

    // Select by the stable preset label, not a date-dependent example.
    await component.getByRole("button", { name: /date format/i }).click();
    await component.getByRole("option", { name: "dd/MM/yyyy HH:mm", exact: true }).click();

    await expect.element(component.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  test("saving triggers the upsert with the selected values", async () => {
    const component = await render(<UserPreferencesCard />);

    await component.getByRole("button", { name: /date format/i }).click();

    await component.getByRole("option", { name: "dd/MM/yyyy HH:mm", exact: true }).click();
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(upsertUserPreferences).toHaveBeenCalledWith({
        dateFormat: "EU_DATETIME",
        timezone: null,
      });
    });
  });

  test("re-selecting the current value clears the override with an explicit-null upsert", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: {
        value: "EU_DATETIME",
        source: "USER",
        inherited: { value: null, source: "DEFAULT" },
      },
      timezone: { value: "UTC", source: "USER", inherited: { value: null, source: "DEFAULT" } },
    });

    const component = await render(<UserPreferencesCard />);

    await expect
      .element(component.getByRole("button", { name: /date format/i }))
      .toHaveTextContent("dd/MM/yyyy HH:mm");

    // Re-selecting the currently-selected value clears the override (maps to null).
    await component.getByRole("button", { name: /date format/i }).click();
    await component.getByRole("option", { name: "dd/MM/yyyy HH:mm", exact: true }).click();
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(vi.mocked(upsertUserPreferences).mock.calls[0]?.[0]).toEqual({
        dateFormat: null,
        timezone: "UTC",
      });
    });
  });

  test("no longer renders a separate 'reset to global' button", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: {
        value: "EU_DATETIME",
        source: "USER",
        inherited: { value: null, source: "DEFAULT" },
      },
      timezone: {
        value: "Europe/Paris",
        source: "GLOBAL",
        inherited: { value: "Europe/Paris", source: "GLOBAL" },
      },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: "Save" })).toBeVisible();
    expect(component.getByRole("button", { name: /reset to global/i }).elements()).toHaveLength(0);
  });

  test("still renders and saves the form when the effective query resolves with no global values", async () => {
    vi.mocked(getEffectivePreferences).mockResolvedValue({
      ...baseEffective,
      dateFormat: { value: null, source: "DEFAULT", inherited: { value: null, source: "DEFAULT" } },
      timezone: { value: null, source: "DEFAULT", inherited: { value: null, source: "DEFAULT" } },
    });

    const component = await render(<UserPreferencesCard />);

    await expect.element(component.getByRole("button", { name: "Save" })).toBeVisible();
    expect(
      component.getByText(/something went wrong when fetching your preferences/i).elements()
    ).toHaveLength(0);

    await component.getByRole("button", { name: /date format/i }).click();

    await component.getByRole("option", { name: "dd/MM/yyyy HH:mm", exact: true }).click();
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(upsertUserPreferences).toHaveBeenCalledWith({
        dateFormat: "EU_DATETIME",
        timezone: null,
      });
    });
  });

  test("shows an error screen when the effective-preferences query fails", async () => {
    vi.mocked(getEffectivePreferences).mockRejectedValue(new Error("network down"));

    const component = await render(<UserPreferencesCard />);

    await expect
      .element(component.getByText(/something went wrong when fetching your preferences/i))
      .toBeVisible();
  });

  test("toasts the error when the save fails", async () => {
    vi.mocked(upsertUserPreferences).mockRejectedValue(new Error("save failed"));

    const component = await render(<UserPreferencesCard />);

    await component.getByRole("button", { name: /date format/i }).click();

    await component.getByRole("option", { name: "dd/MM/yyyy HH:mm", exact: true }).click();
    await component.getByRole("button", { name: "Save" }).click();

    await expect.element(component.getByText("save failed")).toBeVisible();
  });
});
