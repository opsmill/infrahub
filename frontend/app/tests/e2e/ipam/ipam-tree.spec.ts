import { expect, test } from "@playwright/test";

test.describe("/ipam - Ipam Tree", () => {
  test("load child tree item when clicking on parent tree item", async ({ page }) => {
    await page.goto("/ipam");
    await expect(page.getByTestId("ipam-tree")).toBeVisible();

    await test.step("all top level prefix are collapsed", async () => {
      await expect(page.getByRole("treeitem", { name: "10.0.0.0/8" })).toBeVisible();
      await expect(page.getByRole("treeitem", { name: "10.1.0.0/16" })).toBeHidden();
    });

    await test.step("view direct children of a top level prefix", async () => {
      await page
        .getByRole("treeitem", { name: "10.0.0.0/8" })
        .getByTestId("tree-item-toggle")
        .click();
      await expect(page.getByRole("treeitem", { name: "10.0.0.0/8" })).toBeVisible();
      await expect(page.getByRole("treeitem", { name: "10.1.0.0/16" })).toBeVisible();
      await expect(page.getByRole("treeitem", { name: "10.1.0.12/31" })).toBeHidden();
    });

    await test.step("view children of a children prefix", async () => {
      await page
        .getByRole("treeitem", { name: "10.1.0.0/16" })
        .getByTestId("tree-item-toggle")
        .click();
      await expect(page.getByRole("treeitem", { name: "10.0.0.0/8" })).toBeVisible();
      await expect(page.getByRole("treeitem", { name: "10.1.0.0/16" })).toBeVisible();
      await expect(page.getByRole("treeitem", { name: "10.1.0.12/31" })).toBeVisible();
    });

    await test.step("On first load, it expands IPAM tree to the selected prefix position", async () => {
      await page.getByRole("treeitem", { name: "10.1.0.12/31" }).click();
      await page.reload();
      await expect(page.getByTestId("ipam-tree")).toBeVisible();
      await expect(page.getByRole("treeitem", { name: "10.0.0.0/8" })).toBeVisible();
      await expect(page.getByRole("treeitem", { name: "10.1.0.0/16" })).toBeVisible();
      await expect(page.getByRole("treeitem", { name: "10.1.0.12/31" })).toBeVisible();
      await expect(page.locator("[aria-selected=true]")).toContainText("10.1.0.12/31");
    });
  });

  test("go to prefix summary when clicking on any tree item", async ({ page }) => {
    await page.goto("/ipam");

    await page.getByTestId("ipam-tree").getByRole("link", { name: "10.0.0.0/8" }).click();
    await expect(page.getByRole("heading", { name: "10.0.0.0/8" })).toBeVisible();
  });

  test("search an IP Prefix", async ({ page }) => {
    await page.goto("/ipam");

    await test.step("search on IPAM tree", async () => {
      await expect(page.getByRole("treeitem", { name: "10.0.0.0/8" })).toBeVisible();
      await page.getByPlaceholder("Filter...").fill("10.2");
      await expect(page.getByRole("treeitem", { name: "10.2.0.0/16" })).toBeVisible();
      expect(await page.getByRole("treeitem").count()).toEqual(1);
    });

    await test.step("search results are visible after navigation", async () => {
      await page.getByRole("treeitem", { name: "10.2.0.0/16" }).click();
      await expect(page.getByRole("heading", { name: "10.2.0.0/16" })).toBeVisible();
      await expect(page.getByRole("treeitem", { name: "10.2.0.0/16" })).toBeVisible();
      expect(await page.getByRole("treeitem").count()).toEqual(1);
    });

    await test.step("reset IPAM search", async () => {
      await page.getByPlaceholder("Filter...").fill("");
      await expect(page.getByRole("treeitem", { name: "10.0.0.0/8" })).toBeVisible();
    });
  });

  test("collapse IPAM tree", async ({ page }) => {
    await page.goto("/ipam");

    await expect(page.getByTestId("ipam-tree")).toBeVisible();
    await page.getByRole("button", { name: "toggle IPAM tree" }).click();
    await expect(page.getByTestId("ipam-tree")).toBeHidden();
    await page.getByRole("button", { name: "toggle IPAM tree" }).click();
    await expect(page.getByTestId("ipam-tree")).toBeVisible();
  });
});
