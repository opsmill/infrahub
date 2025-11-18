import { expect, test } from "@playwright/test";

test.describe("/ipam - Ipam Tree", () => {
  test("load child tree item when clicking on parent tree item", async ({ page }) => {
    await page.goto("/ipam");
    const ipamTree = page.getByRole("treegrid", { name: "IPAM tree" });

    await test.step("all top level prefix are collapsed", async () => {
      await expect(ipamTree.getByText("10.0.0.0/8")).toBeVisible();
      await expect(ipamTree.getByText("10.1.0.0/16")).toBeHidden();
    });

    await test.step("view direct children of a top level prefix", async () => {
      await ipamTree.getByRole("button", { name: "Expand 10.0.0.0/8" }).click();
      await expect(ipamTree.getByText("10.0.0.0/8")).toBeVisible();
      await expect(ipamTree.getByText("10.1.0.0/16")).toBeVisible();
      await expect(ipamTree.getByText("10.1.0.12/31")).toBeHidden();
    });

    await test.step("view children of a children prefix", async () => {
      await ipamTree.getByRole("button", { name: "Expand 10.1.0.0/16" }).click();
      await expect(ipamTree.getByText("10.0.0.0/8")).toBeVisible();
      await expect(ipamTree.getByText("10.0.0.0/8")).toBeVisible();
      await expect(ipamTree.getByText("10.1.0.0/16")).toBeVisible();
      await expect(ipamTree.getByText("10.1.0.12/31")).toBeVisible();
    });

    await test.step("On first load, it expands IPAM tree to the selected prefix position", async () => {
      await ipamTree.getByText("10.1.0.12/31").click();
      await expect(page.getByRole("heading", { name: "10.1.0.12/31" })).toBeVisible();
      await page.reload();
      await expect(ipamTree.getByText("10.0.0.0/8")).toBeVisible();
      await expect(ipamTree.getByText("10.1.0.0/16")).toBeVisible();
      await expect(ipamTree.getByText("10.1.0.12/31")).toBeVisible();
      await expect(ipamTree.getByRole("row", { name: "10.1.0.12/31" })).toContainClass(
        "bg-neutral-100"
      );
    });
  });

  test("go to prefix summary when clicking on any tree item", async ({ page }) => {
    await page.goto("/ipam");

    await page.getByLabel("IPAM tree").getByText("10.0.0.0/8").click();
    await expect(page.getByRole("heading", { name: "10.0.0.0/8" })).toBeVisible();
  });

  test("search an IP Prefix", async ({ page }) => {
    await page.goto("/ipam");
    const ipamTree = page.getByRole("treegrid", { name: "IPAM tree" });

    await test.step("search on IPAM tree", async () => {
      await expect(ipamTree.getByText("10.0.0.0/8")).toBeVisible();
      await page.getByRole("searchbox", { name: "IPAM Tree search" }).fill("10.2");
      await expect(ipamTree.getByText("10.2.0.0/16")).toBeVisible();
      expect(await ipamTree.getByRole("row").count()).toEqual(1);
    });

    await test.step("search results are visible after navigation", async () => {
      await ipamTree.getByText("10.2.0.0/16").click();
      await expect(page.getByRole("heading", { name: "10.2.0.0/16" })).toBeVisible();
      await expect(ipamTree.getByText("10.2.0.0/16")).toBeVisible();
      expect(await ipamTree.getByRole("row").count()).toEqual(1);
    });

    await test.step("reset IPAM search", async () => {
      await page.getByRole("searchbox", { name: "IPAM Tree search" }).fill("");
      await expect(ipamTree.getByText("10.0.0.0/8")).toBeVisible();
    });
  });

  test("collapse IPAM tree", async ({ page }) => {
    await page.goto("/ipam");
    const ipamTree = page.getByRole("treegrid", { name: "IPAM tree" });

    await expect(ipamTree).toBeVisible();
    await page.getByRole("button", { name: "toggle IPAM tree" }).click();
    await expect(ipamTree).toBeHidden();
    await page.getByRole("button", { name: "toggle IPAM tree" }).click();
    await expect(ipamTree).toBeVisible();
  });
});
