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

    await test.step("On first load, it expands IPAM tree to the selected prefix position", async () => {
      await page.getByRole("treeitem", { name: "10.1.0.12/31" }).click();
      await page.reload();
      await expect(page.getByTestId("ipam-tree")).toBeVisible();
      await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(17);
      await expect(page.locator("[aria-selected=true]")).toContainText("10.1.0.12/31");
    });
  });

  test("go to prefix summary when clicking on any tree item", async ({ page }) => {
    await page.goto("/ipam");

    await page.getByTestId("ipam-tree").getByRole("link", { name: "10.0.0.0/8" }).click();
    expect(page.url()).toContain("/ipam/prefixes/");
    await expect(page.getByText("Ipam IP Prefix summary")).toBeVisible();
    await expect(page.getByText("Prefix10.0.0.0/8")).toBeVisible();
  });
});
