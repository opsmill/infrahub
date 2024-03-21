import { expect, test } from "@playwright/test";

const OBJECT_NAME = "atl1-core1";
const SEARCH = "atl";
const INITIAL_AMOUNT = "20";
const SEARCHED_AMOUNT = "4";

test.describe("Object list search", async () => {
  test("verify the search", async ({ page }) => {
    await page.goto("/objects/InfraDevice");

    await test.step("should access object list and verify the total amount of results", async () => {
      await expect(page.locator("tbody")).toContainText(OBJECT_NAME);
      await page.getByText(INITIAL_AMOUNT, { exact: true }).click();
      await expect(page.getByRole("main")).toContainText(INITIAL_AMOUNT);
    });

    await test.step("should search an object and verify the total amount of results", async () => {
      await page.getByTestId("object-list-search-bar").click();
      await page.getByTestId("object-list-search-bar").fill(SEARCH);
      await expect(page.locator("tbody")).toContainText(OBJECT_NAME);
      await expect(page.getByRole("main")).toContainText(SEARCHED_AMOUNT);
    });
  });
});
