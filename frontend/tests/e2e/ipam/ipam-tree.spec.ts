import { expect, test } from "@playwright/test";

test.describe("/ipam - Ipam Tree", () => {
  test("load child tree item when clicking on parent tree item", async ({ page }) => {
    await page.goto("/ipam");

    await expect(page.getByRole("heading", { name: "Navigation" })).toBeVisible();
    await expect(page.getByTestId("ipam-tree")).toBeVisible();
    await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(4);

    await page
      .getByRole("treeitem", { name: "10.0.0.0/8" })
      .getByTestId("tree-item-toggle")
      .click();
    await expect(page.getByRole("treeitem", { name: "10.1.0.0/16" })).toBeVisible();
    await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(7);

    await page
      .getByRole("treeitem", { name: "10.1.0.0/16" })
      .getByTestId("tree-item-toggle")
      .click();
    await expect(page.getByRole("treeitem", { name: "10.1.0.12/31" })).toBeVisible();
    await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(17);
  });

  test("On first load, it expands IPAM tree to the selected prefix position", async ({ page }) => {
    await page.goto("/ipam/prefixes/10.1.0.16%2F31");
  });
});
