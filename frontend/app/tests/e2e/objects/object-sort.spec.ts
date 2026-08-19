import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Object sort", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should customize sort, combine multiple sorts, and reset to default", async ({ page }) => {
    const sortButton = page.getByRole("button", { name: /^Sort( \d+)?$/ });
    const sortRows = page.getByRole("grid", { name: "Sort keys" }).getByRole("row");
    const firstRowLink = page.getByTestId("data-table-row").first().getByRole("link").first();

    await test.step("navigate and verify the schema default order", async () => {
      await page.goto("/objects/InfraDevice");
      await expect(page.getByRole("heading", { name: "Device" })).toBeVisible();
      await expect(firstRowLink).toHaveText("atl1-core1");
    });

    await test.step("open the sort editor showing the schema default", async () => {
      await sortButton.click();
      await expect(page.getByText("Default order · applied now")).toBeVisible();
      await expect(page.getByRole("button", { name: /Sort field/ })).toContainText("Name");
      await expect(page.getByRole("button", { name: /Sort direction/ })).toContainText("Ascending");
      await expect(
        page.getByRole("button", { name: "Why this sort can't be removed" })
      ).toBeVisible();
    });

    await test.step("switch the direction to descending", async () => {
      await page.getByRole("button", { name: /Sort direction/ }).click();
      await page.getByRole("option", { name: "Descending" }).click();

      await expect(page.getByText("Custom order")).toBeVisible();
      await expect(page).toHaveURL(/sort=name__value__desc/);
      await expect(sortButton).toContainText("1");
      await expect(firstRowLink).toHaveText("ord1-leaf2");
    });

    await test.step("add a secondary sort on a relationship field", async () => {
      await page.getByRole("button", { name: "Add sort" }).click();

      await page.getByPlaceholder("Search...").fill("nonexistent field");
      await expect(page.getByText("No fields match")).toBeVisible();
      await page.getByPlaceholder("Search...").fill("");

      await page.getByRole("menuitem", { name: "Site" }).click();
      await page.getByRole("menuitem", { name: "Name", exact: true }).click();
      await page.getByRole("menuitem", { name: "Ascending" }).click();

      await expect(sortRows).toHaveCount(2);
      await expect(sortButton).toContainText("2");
      await expect(page).toHaveURL(/sort=name__value__desc(,|%2C)site__name__value__asc/);
      // The primary sort is unchanged, so the first row stays the same.
      await expect(firstRowLink).toHaveText("ord1-leaf2");
    });

    await test.step("add a metadata sort from the search results", async () => {
      await page.getByRole("button", { name: "Add sort" }).click();
      await page.getByPlaceholder("Search...").fill("updated");
      await page.getByRole("menuitem", { name: "Updated at" }).click();
      await page.getByRole("menuitem", { name: "Descending" }).click();

      await expect(sortRows).toHaveCount(3);
      await expect(sortButton).toContainText("3");
      await expect(page).toHaveURL(
        /sort=name__value__desc(,|%2C)site__name__value__asc(,|%2C)node_metadata__updated_at__desc/
      );
    });

    await test.step("remove the primary and metadata sorts", async () => {
      await sortRows.first().getByRole("button", { name: "Remove sort" }).click();

      await expect(sortRows).toHaveCount(2);
      await expect(page).not.toHaveURL(/name__value__desc/);
      await expect(firstRowLink).toHaveText(/^atl1-/);

      await sortRows.last().getByRole("button", { name: "Remove sort" }).click();

      await expect(sortRows).toHaveCount(1);
      await expect(sortButton).toContainText("1");
      await expect(page).toHaveURL(/sort=site__name__value__asc/);
      await expect(page).not.toHaveURL(/node_metadata__updated_at/);
    });

    await test.step("change the sort field from the row select", async () => {
      await page.getByRole("button", { name: /Sort field/ }).click();
      await page.getByPlaceholder("Search...").fill("name");
      await page.getByRole("option", { name: "Name", exact: true }).click();

      await expect(page).toHaveURL(/sort=name__value__asc/);
      await expect(firstRowLink).toHaveText("atl1-core1");
    });

    await test.step("reset to the default order", async () => {
      // Both the header button and the row button are named "Reset to default";
      // the header one comes first in DOM order.
      await page.getByRole("button", { name: "Reset to default" }).first().click();

      await expect(page.getByText("Default order · applied now")).toBeVisible();
      await expect(page).not.toHaveURL(/sort=/);
      await expect(sortButton).not.toContainText("1");
      await expect(firstRowLink).toHaveText("atl1-core1");
    });
  });
});
