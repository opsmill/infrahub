import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Object header sort", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should sort from the column header, persist on reload, and toggle-clear", async ({
    page,
  }) => {
    const firstRowLink = page.getByTestId("data-table-row").first().getByRole("link").first();
    const nameHeader = page.getByTestId("object-items").getByRole("button", { name: "Name" });

    await test.step("navigate and verify the schema default order", async () => {
      await page.goto("/objects/InfraDevice");
      await expect(page.getByRole("heading", { name: "Device" })).toBeVisible();
      await expect(firstRowLink).toHaveText("atl1-core1");
    });

    await test.step("sort descending from the Name header", async () => {
      await nameHeader.click();
      await page.getByRole("menuitemradio", { name: "Sort descending" }).click();

      await expect(page).toHaveURL(/sort=name__value__desc/);
      await expect(firstRowLink).toHaveText("ord1-leaf2");
      await expect(page.getByRole("button", { name: "Name sorted descending" })).toBeVisible();
    });

    await test.step("reload and verify the sort persists", async () => {
      await page.reload();
      await expect(page).toHaveURL(/sort=name__value__desc/);
      await expect(firstRowLink).toHaveText("ord1-leaf2");
      await expect(page.getByRole("button", { name: "Name sorted descending" })).toBeVisible();
    });

    await test.step("toggle-clear restores the default order", async () => {
      await nameHeader.click();
      await page.getByRole("menuitemradio", { name: "Sort descending" }).click();

      await expect(page).not.toHaveURL(/sort=/);
      await expect(firstRowLink).toHaveText("atl1-core1");
      await expect(page.getByRole("button", { name: "Name sorted descending" })).not.toBeVisible();
    });
  });

  test("should replace a toolbar-built multi-field sort with a single-field sort", async ({
    page,
  }) => {
    const sortButton = page.getByRole("button", { name: /^Sort( \d+)?$/ });
    const sortRows = page.getByRole("grid", { name: "Sort keys" }).getByRole("row");
    const nameHeader = page.getByTestId("object-items").getByRole("button", { name: "Name" });

    await test.step("navigate to the device list", async () => {
      await page.goto("/objects/InfraDevice");
      await expect(page.getByRole("heading", { name: "Device" })).toBeVisible();
    });

    await test.step("build a two-field sort in the toolbar sort editor", async () => {
      await sortButton.click();
      await page.getByRole("button", { name: /Sort direction/ }).click();
      await page.getByRole("option", { name: "Descending" }).click();

      await page.getByRole("button", { name: "Add sort" }).click();
      await page.getByRole("menuitem", { name: "Site" }).click();
      await page.getByRole("menuitem", { name: "Name", exact: true }).click();
      await page.getByRole("menuitem", { name: "Ascending" }).click();

      await expect(sortRows).toHaveCount(2);
      await expect(page).toHaveURL(/sort=name__value__desc(,|%2C)site__name__value__asc/);
      await page.keyboard.press("Escape");
    });

    await test.step("sort ascending from the Name header", async () => {
      await nameHeader.click();
      await page.getByRole("menuitemradio", { name: "Sort ascending" }).click();

      await expect(page).toHaveURL(/sort=name__value__asc/);
      await expect(page).not.toHaveURL(/site__name__value__asc/);
      await expect(page.getByRole("button", { name: "Name sorted ascending" })).toBeVisible();
    });

    await test.step("verify the toolbar sort editor shows exactly the header sort", async () => {
      await sortButton.click();
      await expect(sortRows).toHaveCount(1);
      await expect(page.getByRole("button", { name: /Sort field/ })).toContainText("Name");
      await expect(page.getByRole("button", { name: /Sort direction/ })).toContainText("Ascending");
    });
  });
});
