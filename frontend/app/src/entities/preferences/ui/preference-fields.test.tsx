import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { Form } from "@/shared/components/ui/form";

import { DateFormatField, toFieldValue } from "@/entities/preferences/ui/preference-fields";

import { render } from "../../../../tests/components/render";

// A late-evening UTC instant: rendered east of UTC it lands on the NEXT calendar day, so an example
// that ignored the timezone could not accidentally match.
const FIXED_INSTANT = new Date("2026-06-11T23:30:00Z");

function renderField({
  timezone,
  fallbackTimezone,
}: {
  timezone: string | null;
  fallbackTimezone?: string | null;
}) {
  return render(
    <Form
      defaultValues={{
        date_format: toFieldValue("ISO_DATETIME"),
        timezone: toFieldValue(timezone),
      }}
      onSubmit={() => {}}
    >
      <DateFormatField fallbackTimezone={fallbackTimezone} />
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
