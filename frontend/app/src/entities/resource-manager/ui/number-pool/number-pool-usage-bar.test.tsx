import { describe, expect, it } from "vitest";
import { page } from "vitest/browser";

import { render } from "../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../tests/components/utils";
import { generateNumberPoolUsage } from "../../../../../tests/fake/number-pool";
import { formatUsagePercent, NumberPoolUsageBar } from "./number-pool-usage-bar";

describe("NumberPoolUsageBar", () => {
  it("shows the share of the range in use", async () => {
    // GIVEN
    const usage = generateNumberPoolUsage({ size: 50, used: 30, utilization: 60 });

    // WHEN
    await render(<NumberPoolUsageBar usage={usage} />);

    // THEN
    await expect.element(page.getByText("60%")).toBeVisible();
  });

  it("shows how many numbers are used out of the range size on hover", async () => {
    // GIVEN
    const usage = generateNumberPoolUsage({ size: 1250, used: 30, utilization: 2.4 });
    const component = await render(<NumberPoolUsageBar usage={usage} />);
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByText("2.4%").hover();

    // THEN
    await expect.element(page.getByRole("tooltip")).toHaveTextContent("Used30 of 1,250");
  });
});

describe("formatUsagePercent", () => {
  it.each([
    [0, "0%"],
    [0.05, "<0.1%"],
    [3, "3%"],
    [3.25, "3.3%"],
    [42.9, "42%"],
  ])("formats %s as %s", (value, expected) => {
    // WHEN
    const label = formatUsagePercent(value);

    // THEN
    expect(label).toBe(expected);
  });
});
