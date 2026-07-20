import { expect, test } from "@playwright/test";

test.describe("/ipam - IP Prefix List Sorting", () => {
  test("should sort IP prefixes from a column header and toggle-clear", async ({ page }) => {
    const prefixTable = page.getByTestId("ip-prefix-table");
    const firstRowLink = prefixTable
      .getByTestId("data-table-row")
      .first()
      .getByRole("link")
      .first();
    const descriptionHeader = prefixTable.getByRole("button", { name: "Description" });

    await test.step("navigate and verify the default prefix order", async () => {
      await page.goto("/ipam");
      await expect(firstRowLink).toHaveText("10.0.0.0/8");
    });

    await test.step("sort descending from the Description header", async () => {
      await descriptionHeader.click();
      await page.getByRole("menuitem", { name: "Sort descending" }).click();

      await expect(page).toHaveURL(/sort=description__value__desc/);
      await expect(firstRowLink).toHaveText("203.111.0.80/29");
      await expect(
        prefixTable.getByRole("button", { name: "Description sorted descending" })
      ).toBeVisible();
    });

    await test.step("toggle-clear restores the default order", async () => {
      await descriptionHeader.click();
      await page.getByRole("menuitem", { name: "Sort descending" }).click();

      await expect(page).not.toHaveURL(/sort=/);
      await expect(firstRowLink).toHaveText("10.0.0.0/8");
      await expect(
        prefixTable.getByRole("button", { name: "Description sorted descending" })
      ).not.toBeVisible();
    });
  });

  test("a custom sort suppresses available IPs and hides the availability toggle", async ({
    page,
  }) => {
    const prefixTable = page.getByTestId("ip-prefix-table");
    const availableRows = prefixTable.getByTestId("ip-prefix-available");
    const availabilityToggle = page.getByText("Available IP prefixes", { exact: true });
    const descriptionHeader = prefixTable.getByRole("button", { name: "Description" });
    const childPrefix = page
      .getByTestId("identifier-cell")
      .getByRole("link", { name: "10.0.0.0/16" });

    await test.step("open a prefix's children where available IPs are interleaved", async () => {
      await page.goto("/ipam");
      await page.getByTestId("identifier-cell").getByRole("link", { name: "10.0.0.0/8" }).click();
      await page.getByRole("link", { name: "Children" }).click();

      await expect(childPrefix).toBeVisible();
      await expect(availableRows.first()).toBeVisible();
      await expect(availabilityToggle).toBeVisible();
    });

    await test.step("applying a custom sort hides available IPs and the toggle", async () => {
      await descriptionHeader.click();
      await page.getByRole("menuitem", { name: "Sort descending" }).click();

      await expect(page).toHaveURL(/sort=description__value__desc/);
      await expect(availableRows).toHaveCount(0);
      await expect(availabilityToggle).not.toBeVisible();
      // Real prefixes are still listed, just without the interleaved available ranges.
      await expect(childPrefix).toBeVisible();
    });

    await test.step("clearing the sort restores available IPs and the toggle", async () => {
      await descriptionHeader.click();
      await page.getByRole("menuitem", { name: "Sort descending" }).click();

      await expect(page).not.toHaveURL(/sort=/);
      await expect(availableRows.first()).toBeVisible();
      await expect(availabilityToggle).toBeVisible();
    });
  });
});
