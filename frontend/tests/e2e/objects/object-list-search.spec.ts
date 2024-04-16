import { expect, test } from "@playwright/test";

const OBJECT_NAME = "atl1-core1";
const SEARCH = "atl";

test.describe("Object list search", async () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("verify the search", async ({ page }) => {
    await page.goto("/objects/InfraDevice");

    await test.step("should access object list and verify the total amount of results", async () => {
      await expect(page.locator("tbody")).toContainText(OBJECT_NAME);
      await expect(page.getByRole("main")).toContainText("Showing 1 to 10 of 20 results");
    });

    await test.step("should search an object and verify the total amount of results", async () => {
      await page.getByTestId("object-list-search-bar").fill(SEARCH);
      await expect(page.locator("tbody")).toContainText(OBJECT_NAME);
      await expect(page.getByRole("main")).toContainText("Showing 1 to 4 of 4 results");
    });
  });
});
