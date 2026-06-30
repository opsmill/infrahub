import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

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
    const component = await render(<TabPreferences />);

    await expect.element(component.getByRole("button", { name: /date format/i })).toBeVisible();
    await expect.element(component.getByRole("combobox", { name: /timezone/i })).toBeVisible();
    expect(component.getByRole("textbox").elements()).toHaveLength(0);
  });

  test("uses the personal card title", async () => {
    const component = await render(<TabPreferences />);

    await expect.element(component.getByText("Personal date and time")).toBeVisible();
  });

  test("lays the fields out as detail rows with a visible label and an accessible control", async () => {
    const component = await render(<TabPreferences />);

    // The controls keep their accessible names even though their own labels are sr-only.
    await expect.element(component.getByRole("button", { name: /date format/i })).toBeVisible();
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

  test("shows the inherited global value as hint when the user has no override", async () => {
    const component = await render(<TabPreferences />);

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

  test("date-format options are labelled by the pattern itself", async () => {
    const component = await render(<TabPreferences />);

    // React Aria mounts the Select's hidden native <select> lazily; it is the only
    // <select> in this form (timezone is a Combobox), so poll for it to appear.
    let dateFormatSelect: HTMLSelectElement | null = null;
    await vi.waitFor(() => {
      dateFormatSelect = component.container.querySelector<HTMLSelectElement>("select");
      if (!dateFormatSelect) throw new Error("date-format <select> not mounted yet");
    });

    const labels = Array.from(dateFormatSelect!.options).map((o) => o.textContent?.trim());

    // The option label is now the pattern/sentinel itself, not a live example.
    expect(labels).toContain("yyyy-MM-dd HH:mm");
    expect(labels).toContain("relative");
  });

  test("shows a live example next to the date-format control that updates on selection", async () => {
    const component = await render(<TabPreferences />);

    // No personal override yet, so no example is shown until a format is picked.
    expect(component.getByText(/^Example:/i).elements()).toHaveLength(0);

    // Frozen at 2026-06-30T14:30:00; the ISO preset renders that instant.
    await selectOption(component, "", { value: "yyyy-MM-dd HH:mm" });
    await expect.element(component.getByText("Example: 2026-06-30 14:30")).toBeVisible();

    // Switching the selection updates the example deterministically.
    await selectOption(component, "", { value: "relative" });
    await expect.element(component.getByText("Example: 2 days ago")).toBeVisible();
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

    // Select by the stable preset key, not the (date-dependent) label.
    await selectOption(component, "", { value: "relative" });
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

    // Select by the stable preset key, not the (date-dependent) label.
    await selectOption(component, "", { value: "relative" });

    await expect.element(component.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  test("saving triggers the upsert with the selected values", async () => {
    const component = await render(<TabPreferences />);

    // Select by the stable preset key, not the (date-dependent) label.
    await selectOption(component, "", { value: "relative" });
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
