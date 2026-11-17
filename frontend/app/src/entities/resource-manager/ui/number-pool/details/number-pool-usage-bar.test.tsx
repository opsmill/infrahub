import { describe, expect, it } from "vitest";
import { page } from "vitest/browser";

import { render } from "../../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../../tests/components/utils";
import { generateNumberPoolUsage } from "../../../../../../tests/fake/number-pool";
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

  it("breaks the share down by branch on hover", async () => {
    // GIVEN
    const usage = generateNumberPoolUsage({
      size: 1250,
      used: 30,
      usedDefaultBranch: 28,
      usedBranches: 2,
      utilization: 2.4,
    });
    const component = await render(<NumberPoolUsageBar usage={usage} />);
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByText("2.4%").hover();

    // THEN
    await expect
      .element(page.getByRole("tooltip"))
      .toHaveTextContent("Default branch28Other branches2Used30 of 1,250");
  });

  it("shows how many numbers a branch segment uses out of the range size on hover", async () => {
    // GIVEN
    const usage = generateNumberPoolUsage({
      size: 50,
      used: 30,
      usedDefaultBranch: 28,
      usedBranches: 2,
    });
    const component = await render(<NumberPoolUsageBar usage={usage} />);
    await initPointerTracking(component.locator);
    const defaultBranchSegment = component.getByRole("progressbar").element().firstElementChild;

    // WHEN
    await page.elementLocator(defaultBranchSegment as HTMLElement).hover();

    // THEN
    await expect.element(page.getByRole("tooltip")).toHaveTextContent("Default branch28 of 50");
  });

  it("shows the exact count used, on a track marked as having no upper limit, when the range has no size", async () => {
    // GIVEN
    const usage = generateNumberPoolUsage({ size: null, used: 2_147_483_647, utilization: null });

    // WHEN
    await render(<NumberPoolUsageBar usage={usage} />);

    // THEN
    await expect.element(page.getByText("2,147,483,647")).toBeVisible();
    await expect.element(page.getByRole("img", { name: "No upper limit" })).toBeVisible();
  });

  it("breaks the count down by branch on hover when the range has no size", async () => {
    // GIVEN
    const usage = generateNumberPoolUsage({
      size: null,
      used: 2_000_000,
      usedDefaultBranch: 0,
      usedBranches: 2_000_000,
      utilization: null,
    });
    const component = await render(<NumberPoolUsageBar usage={usage} />);
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByText("2,000,000", { exact: true }).hover();

    // THEN
    await expect
      .element(page.getByRole("tooltip"))
      .toHaveTextContent("Default branch0Other branches2,000,000Used2,000,000");
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
