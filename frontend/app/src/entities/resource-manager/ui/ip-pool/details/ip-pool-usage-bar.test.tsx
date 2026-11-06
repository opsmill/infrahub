import { describe, expect, it } from "vitest";
import { page } from "vitest/browser";

import { render } from "../../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../../tests/components/utils";
import { generateIpPoolResourceUsage } from "../../../../../../tests/fake/ip-pool";
import { IpPoolUsageBar } from "./ip-pool-usage-bar";

describe("IpPoolUsageBar", () => {
  it("shows the share of the resource prefix in use", async () => {
    // GIVEN
    const usage = generateIpPoolResourceUsage({ utilization: 60 });

    // WHEN
    await render(<IpPoolUsageBar usage={usage} />);

    // THEN
    await expect.element(page.getByText("60%")).toBeVisible();
  });

  it("shows the default-branch share on hover of the first segment", async () => {
    // GIVEN
    const usage = generateIpPoolResourceUsage({
      utilization: 60,
      utilizationDefaultBranch: 40,
      utilizationBranches: 20,
    });
    const component = await render(<IpPoolUsageBar usage={usage} />);
    await initPointerTracking(component.locator);
    const defaultBranchSegment = component.getByRole("progressbar").element().firstElementChild;

    // WHEN
    await page.elementLocator(defaultBranchSegment as HTMLElement).hover();

    // THEN
    await expect.element(page.getByRole("tooltip")).toHaveTextContent("Default branch40%");
  });

  it("shows the share this branch adds on hover of the second segment", async () => {
    // GIVEN
    const usage = generateIpPoolResourceUsage({
      utilization: 60,
      utilizationDefaultBranch: 40,
      utilizationBranches: 20,
    });
    const component = await render(<IpPoolUsageBar usage={usage} />);
    await initPointerTracking(component.locator);
    const branchSegment = component.getByRole("progressbar").element().lastElementChild;

    // WHEN
    await page.elementLocator(branchSegment as HTMLElement).hover();

    // THEN
    await expect.element(page.getByRole("tooltip")).toHaveTextContent("This branch only20%");
  });

  it("rounds a share below a tenth of a percent to <0.1%", async () => {
    // GIVEN
    const usage = generateIpPoolResourceUsage({
      utilization: 0.05,
      utilizationDefaultBranch: 0.05,
      utilizationBranches: 0,
    });

    // WHEN
    await render(<IpPoolUsageBar usage={usage} />);

    // THEN
    await expect.element(page.getByText("<0.1%")).toBeVisible();
  });
});
