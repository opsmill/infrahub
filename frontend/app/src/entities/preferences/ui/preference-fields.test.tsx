import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { Form } from "@/shared/components/ui/form";

import type { EffectivePreference } from "@/entities/preferences/domain/model/preference";
import { DateFormatField, toFieldValue } from "@/entities/preferences/ui/preference-fields";

import { render } from "../../../../tests/components/render";
import { closeTooltip, initPointerTracking } from "../../../../tests/components/utils";

// Late-evening UTC: east of UTC this lands on the NEXT calendar day, so an example that ignored
// the timezone cannot match by accident.
const FIXED_INSTANT = new Date("2026-06-11T23:30:00Z");

const GLOBAL_DATE_FORMAT: EffectivePreference = {
  value: "EU_DATETIME",
  source: "GLOBAL",
  inherited: { value: "EU_DATETIME", source: "GLOBAL" },
};

// Shared by both zones below, whose whole point is that this string does not depend on the
// timezone the form holds.
const EXPECTED_TOOLTIP = "Your preference, overriding the organisation default: dd/MM/yyyy HH:mm.";

function renderField({
  timezone,
  fallbackTimezone,
  preference,
}: {
  timezone: string | null;
  fallbackTimezone?: string | null;
  preference?: EffectivePreference;
}) {
  return render(
    <Form
      defaultValues={{
        date_format: toFieldValue("ISO_DATETIME"),
        timezone: toFieldValue(timezone),
      }}
      onSubmit={() => {}}
    >
      <DateFormatField fallbackTimezone={fallbackTimezone} preference={preference} />
    </Form>
  );
}

describe("DateFormatField example", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(FIXED_INSTANT);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("renders in the timezone held by the form, not the one it would fall back to", async () => {
    const component = await renderField({ timezone: "UTC", fallbackTimezone: "Asia/Tokyo" });

    await expect.element(component.getByText("Example: 2026-06-11 23:30")).toBeVisible();
  });

  test("renders in the fallback timezone while the form's timezone field is empty", async () => {
    const component = await renderField({ timezone: null, fallbackTimezone: "Asia/Tokyo" });

    await expect.element(component.getByText("Example: 2026-06-12 08:30")).toBeVisible();
  });
});

// Both the example and the tooltip preview what saving would produce, but only the example depends
// on the timezone field.
describe("DateFormatField tooltip", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(FIXED_INSTANT);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("names the organisation default while the example follows the fallback timezone", async () => {
    const component = await renderField({
      timezone: null,
      fallbackTimezone: "Asia/Tokyo",
      preference: GLOBAL_DATE_FORMAT,
    });

    await expect.element(component.getByText("Example: 2026-06-12 08:30")).toBeVisible();

    await initPointerTracking(component.locator);
    await component.getByRole("button", { name: "Where this value comes from" }).hover();

    await expect.element(component.getByRole("tooltip", { name: EXPECTED_TOOLTIP })).toBeVisible();

    await closeTooltip(component.locator);
  });

  test("keeps that tooltip identical when the form's timezone moves the example", async () => {
    const component = await renderField({
      timezone: "UTC",
      fallbackTimezone: "Asia/Tokyo",
      preference: GLOBAL_DATE_FORMAT,
    });

    // Same instant, a different zone: the example moved back a calendar day.
    await expect.element(component.getByText("Example: 2026-06-11 23:30")).toBeVisible();

    await initPointerTracking(component.locator);
    await component.getByRole("button", { name: "Where this value comes from" }).hover();

    await expect.element(component.getByRole("tooltip", { name: EXPECTED_TOOLTIP })).toBeVisible();

    await closeTooltip(component.locator);
  });
});
