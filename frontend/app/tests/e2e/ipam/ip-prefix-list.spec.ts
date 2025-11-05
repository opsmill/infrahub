import { expect, test } from "@playwright/test";

test.describe("/ipam/ip_prefixes - Ip Prefix list", () => {
  test("view the prefix list, use the pagination and view prefix summary", async ({ page }) => {
    await page.goto("/ipam");
    await page
      .getByTestId("ip-prefix-table")
      .getByTestId("identifier-cell")
      .getByRole("link", { name: "203.111.0.0/16" })
      .click();
    await page.getByRole("link", { name: "Details" }).click();
    await expect(page.getByRole("heading", { name: "Details" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Activities" })).toBeVisible();
    await expect(page.getByRole("row", { name: "Prefix 203.111.0.0/16" })).toBeVisible();
    await expect(page.getByRole("row", { name: "Utilization 0%" })).toBeVisible();
    await expect(page.getByRole("progressbar")).toBeVisible();
    await expect(page.getByRole("row", { name: "IP Namespace default" })).toBeVisible();
  });

  test("view all sub-prefixes of a given prefix", async ({ page }) => {
    await page.goto("/ipam");

    await test.step("select a prefix to view all sub prefixes", async () => {
      await page.getByRole("treeitem", { name: "2001:db8::/100" }).click();
      await expect(page.getByRole("heading", { name: "2001:db8::/100" })).toBeVisible();
      await expect(page.getByTestId("ip-prefix-table")).toBeVisible();
    });

    await test.step("go to any sub prefix list of any children prefix", async () => {
      await page.getByRole("link", { name: "2001:db8::/110" }).click();
      await expect(page.getByRole("heading", { name: "2001:db8::/110" })).toBeVisible();
      await expect(page.getByTestId("ip-address-table")).toBeVisible();
    });

    await test.step("use breadcrumb to go back to parent prefix", async () => {
      await page
        .getByLabel("IPAM navigation breadcrumb")
        .getByRole("link", { name: "2001:db8::/100" })
        .click();
    });
    await expect(page.getByRole("heading", { name: "2001:db8::/100" })).toBeVisible();
  });

  test("display error message when schema is not found", async ({ page }) => {
    await page.goto("/ipam/IpamIPPrefix/YYY");
    await expect(page.getByText("Cannot find IP Prefix with id YYY")).toBeVisible();
  });

  test("display error message when prefix id is not found", async ({ page }) => {
    await page.goto("/ipam/XXX/YYY");
    await expect(page.getByText("Schema for XXX not found.")).toBeVisible();
  });

  test("search prefixes using text search", async ({ page }) => {
    await page.goto("/ipam");
    await expect(page.getByTestId("ip-prefix-table")).toContainText("10.0.0.0/8");

    await test.step("enter search term and verify filtered results", async () => {
      await page.getByRole("searchbox", { name: "Search" }).fill("2001");
      await expect(page.getByTestId("ip-prefix-table")).toContainText("2001:db8::/100");
      await expect(page.getByTestId("ip-prefix-table")).toContainText("2001:db8::14:0/110");
      await expect(page.getByTestId("ip-prefix-table")).not.toContainText("10.0.0.0/8");
    });

    await test.step("clear search and verify all results return", async () => {
      await page.getByRole("button", { name: "Clear filters" }).click();
      await expect(page.getByTestId("ip-prefix-table")).toContainText("10.0.0.0/8");
    });
  });
});
