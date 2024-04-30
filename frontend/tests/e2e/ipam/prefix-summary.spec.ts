import { expect, test } from "@playwright/test";

test.describe("/ipam/prefixes/:prefix_id - Prefix summary", () => {
  test("go to prefix summary when clicking on any tree item", async ({ page }) => {
    await page.goto("/ipam");
    await page.getByTestId("ipam-tree").getByRole("link", { name: "10.0.0.0/8" }).click();
    expect(page.url()).toContain("/ipam/prefixes/");
    await expect(page.getByText("Ipam IPPrefix summary")).toBeVisible();
    await expect(page.getByText("Prefix10.0.0.0/8")).toBeVisible();
    await expect(page.getByText("Utilization4%")).toBeVisible();
    await expect(page.getByRole("progressbar")).toBeVisible();
    await expect(page.getByText("Ip Namespacedefault")).toBeVisible();

    await test.step("go to all prefixes with breadcrumb", async () => {
      await page.getByRole("link", { name: "All Prefixes" }).click();
      expect(page.url()).toContain("/ipam/prefixes");
    });
  });
});
