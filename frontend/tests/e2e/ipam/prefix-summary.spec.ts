import { expect, test } from "@playwright/test";

test.describe("/ipam/prefixes/:prefixId - Prefix summary", () => {
  test("go to prefix summary when clicking on any tree item", async ({ page }) => {
    await page.goto("/ipam");
    await page.getByTestId("ipam-tree").getByRole("link", { name: "10.0.0.0/8" }).click();
    expect(page.url()).toContain("/ipam/prefixes/");
    await expect(page.getByText("Ipam IP Prefix summary")).toBeVisible();
    await expect(page.getByText("Prefix10.0.0.0/8")).toBeVisible();
    await expect(page.getByText("Utilization1%")).toBeVisible();
    await expect(page.getByRole("progressbar")).toBeVisible();
    await expect(page.getByText("Ip Namespacedefault")).toBeVisible();

    await test.step("go to all prefixes with breadcrumb", async () => {
      await page.getByRole("link", { name: "All Prefixes" }).click();
      expect(page.url()).toContain("/ipam/prefixes");
    });
  });

  test("display error message when prefix id is not found", async ({ page }) => {
    await page.goto("/ipam/prefixes/bad-id");

    await expect(page.getByTestId("ipam-main-content")).toContainText(
      "Prefix with id bad-id not found."
    );
  });
});
