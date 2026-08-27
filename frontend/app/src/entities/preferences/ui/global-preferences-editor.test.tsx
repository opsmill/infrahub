import { format } from "date-fns";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { GlobalPreferences } from "@/entities/preferences/domain/model/preference";
import { getGlobalPreferences } from "@/entities/preferences/domain/use-cases/get-global-preferences";
import { updateGlobalPreference } from "@/entities/preferences/domain/use-cases/update-global-preference";

import { render } from "../../../../tests/components/render";
import { GlobalPreferencesEditor } from "./global-preferences-editor";

vi.mock("@/entities/preferences/domain/use-cases/get-global-preferences");
vi.mock("@/entities/preferences/domain/use-cases/update-global-preference");

// Late-evening UTC: in the global zone (UTC+9) this lands on the NEXT calendar day, so an example
// that ignored the timezone being edited cannot match by accident.
const FIXED_INSTANT = new Date("2026-06-11T23:30:00Z");

const baseGlobal: GlobalPreferences = { dateFormat: null, timezone: "Asia/Tokyo" };

describe("GlobalPreferencesEditor", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(FIXED_INSTANT);
    vi.clearAllMocks();
    vi.mocked(getGlobalPreferences).mockResolvedValue(baseGlobal);
    vi.mocked(updateGlobalPreference).mockResolvedValue();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("uses the global card title", async () => {
    const component = await render(<GlobalPreferencesEditor />);

    await expect.element(component.getByText("Global date and time")).toBeVisible();
  });

  test("renders the card wide enough (max-w-3xl) for the inline date-format example", async () => {
    const component = await render(<GlobalPreferencesEditor />);

    await expect.element(component.getByText("Global date and time")).toBeVisible();

    const title = component.getByText("Global date and time").element() as HTMLElement;
    const card = title.closest(".max-w-3xl");
    expect(card).not.toBeNull();
    expect(card?.className).not.toMatch(/max-w-2xl/);
  });

  test("shows the live date-format example inline next to the control", async () => {
    const component = await render(<GlobalPreferencesEditor />);

    await component.getByRole("button", { name: /date format/i }).click();

    await component.getByRole("option", { name: "yyyy-MM-dd HH:mm", exact: true }).click();

    const combobox = component.getByRole("button", { name: /date format/i }).element();
    const example = component.getByText("Example: 2026-06-12 08:30").element();

    const row = combobox.closest("div.flex.items-center") as HTMLElement;
    expect(row).not.toBeNull();
    expect(row.contains(example)).toBe(true);
  });

  test("renders the example in the global timezone being edited", async () => {
    const component = await render(<GlobalPreferencesEditor />);

    await component.getByRole("button", { name: /date format/i }).click();
    await component.getByRole("option", { name: "yyyy-MM-dd HH:mm", exact: true }).click();

    await expect.element(component.getByText("Example: 2026-06-12 08:30")).toBeVisible();
  });

  test("renders the example in the browser zone when the global timezone is unset", async () => {
    vi.mocked(getGlobalPreferences).mockResolvedValue({ dateFormat: null, timezone: null });

    const component = await render(<GlobalPreferencesEditor />);

    await component.getByRole("button", { name: /date format/i }).click();
    await component.getByRole("option", { name: "yyyy-MM-dd HH:mm", exact: true }).click();

    // An unset global timezone means "the browser's" for every viewer, not the editing admin's zone.
    await expect
      .element(component.getByText(`Example: ${format(FIXED_INSTANT, "yyyy-MM-dd HH:mm")}`))
      .toBeVisible();
  });

  test("previews the browser's own rendering while no global date format is set", async () => {
    const component = await render(<GlobalPreferencesEditor />);

    // Nothing to inherit at the global layer, so an unset format previews the locale rendering
    // every viewer would get — in the global zone being edited.
    const browserRendering = FIXED_INSTANT.toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Asia/Tokyo",
    });

    await expect.element(component.getByText(`Example: ${browserRendering}`)).toBeVisible();
  });

  test("edits the raw global values via the global mutation", async () => {
    const component = await render(<GlobalPreferencesEditor />);

    await component.getByRole("button", { name: /date format/i }).click();

    await component.getByRole("option", { name: "dd/MM/yyyy HH:mm", exact: true }).click();
    await component.getByRole("button", { name: "Save" }).click();

    await vi.waitFor(() => {
      expect(vi.mocked(updateGlobalPreference).mock.calls[0]?.[0]).toEqual({
        dateFormat: "EU_DATETIME",
        timezone: "Asia/Tokyo",
      });
    });
  });

  test("prefills the form from the raw GLOBAL scope values", async () => {
    vi.mocked(getGlobalPreferences).mockResolvedValue({
      dateFormat: "ISO_DATETIME",
      timezone: "Europe/Paris",
    });

    const component = await render(<GlobalPreferencesEditor />);

    await expect
      .element(component.getByRole("button", { name: /date format/i }))
      .toHaveTextContent("yyyy-MM-dd HH:mm");
    await expect
      .element(component.getByRole("button", { name: /timezone/i }))
      .toHaveTextContent("Europe/Paris");
  });
});
