import { describe, expect, test } from "vitest";

import { DetailRow } from "@/shared/components/display/detail-row";

import { render } from "../../../../tests/components/render";

describe("DetailRow", () => {
  test("renders the label, an mdi icon, and the value in a two-column grid", async () => {
    const component = await render(
      <DetailRow icon="mdi:calendar-text" label="Date format">
        <span>2026-06-30</span>
      </DetailRow>
    );

    await expect.element(component.getByText("Date format")).toBeVisible();
    await expect.element(component.getByText("2026-06-30")).toBeVisible();

    const row = component.container.querySelector("dl.grid");
    expect(row?.className).toContain("grid-cols-[200px_auto]");
    expect(component.container.querySelector("dt iconify-icon")).not.toBeNull();
  });

  test("gives the label an id when labelId is provided so a control can reference it", async () => {
    const component = await render(
      <DetailRow label="Timezone" labelId="tz-label">
        <span>UTC</span>
      </DetailRow>
    );

    const labelled = component.container.querySelector("#tz-label");
    expect(labelled?.textContent).toBe("Timezone");
  });

  test("accepts a ReactNode icon", async () => {
    const component = await render(
      <DetailRow icon={<span data-testid="custom-icon" />} label="Field">
        <span>value</span>
      </DetailRow>
    );

    expect(component.container.querySelector('[data-testid="custom-icon"]')).not.toBeNull();
  });
});
