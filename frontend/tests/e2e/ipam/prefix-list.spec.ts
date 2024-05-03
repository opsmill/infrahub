import { expect, test } from "@playwright/test";

test.describe("/ipam/prefixes - Prefix list", () => {
  test("view the prefix list, use the pagination and view prefix summary", async ({ page }) => {
    await page.goto("/ipam/prefixes");
    await page.getByTestId("select-open-option-button").click();
    await page.getByRole("option", { name: "20" }).click();
    await page
      .getByTestId("ipam-main-content")
      .getByRole("row", { name: "203.0.113.0/24 - prefix" }) // prefix need pagination to be visible
      .getByRole("link", { name: "203.0.113.0/24" }) // prefix need pagination to be visible
      .click();
    expect(page.url()).toContain("/ipam/prefixes/");
    await expect(page.getByText("Ipam IP Prefix summary")).toBeVisible();
    await expect(page.getByText("Prefix203.0.113.0/24")).toBeVisible();
    await expect(page.getByText("Utilization93%")).toBeVisible();
    await expect(page.getByRole("progressbar")).toBeVisible();
    await expect(page.getByText("Ip Namespacedefault")).toBeVisible();
  });

  test("view all sub-prefixes of a given prefix", async ({ page }) => {
    await page.goto("/ipam/prefixes?ipam-tab=prefix-details");
    await expect(page.getByTestId("ipam-main-content")).toContainText(
      "Select a Prefix in the Tree to the left to see details"
    );

    await test.step("select a prefix to view all sub prefixes", async () => {
      await page.getByRole("treeitem", { name: "2001:db8::/112" }).click();
      await expect(page.getByTestId("ipam-main-content")).toContainText("2001:db8::/112");
      await expect(page.getByTestId("ipam-main-content")).toContainText("Showing 1 to ");
    });

    await test.step("to to any sub prefix list of any children prefix", async () => {
      await page.getByRole("link", { name: "2001:db8::/120" }).click();
      await expect(page.getByTestId("ipam-main-content")).toContainText("Showing 0 of 0 results");
      await expect(page.url()).toContain("ipam-tab=prefix-details");
    });

    await test.step("use breadcrumb to go back to parent prefix", async () => {
      await page
        .getByTestId("ipam-main-content")
        .getByRole("link", { name: "2001:db8::/112" })
        .click();
      await expect(page.getByTestId("ipam-main-content")).toContainText("Showing 1 to ");
      await expect(page.url()).toContain("ipam-tab=prefix-details");
    });
  });
});
