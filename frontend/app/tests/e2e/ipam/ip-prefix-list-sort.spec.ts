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
      await page.getByRole("menuitemradio", { name: "Sort descending" }).click();

      await expect(page).toHaveURL(/sort=description__value__desc/);
      await expect(firstRowLink).toHaveText("203.111.0.80/29");
      await expect(
        prefixTable.getByRole("button", { name: "Description sorted descending" })
      ).toBeVisible();
    });

    await test.step("toggle-clear restores the default order", async () => {
      await descriptionHeader.click();
      await page.getByRole("menuitemradio", { name: "Sort descending" }).click();

      await expect(page).not.toHaveURL(/sort=/);
      await expect(firstRowLink).toHaveText("10.0.0.0/8");
      await expect(
        prefixTable.getByRole("button", { name: "Description sorted descending" })
      ).not.toBeVisible();
    });
  });
});
