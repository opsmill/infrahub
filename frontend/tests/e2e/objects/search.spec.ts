import { expect, test } from "@playwright/test";

const OBJECT_SEARCH = "atl1-edge1";

test.describe("when searching an object", () => {
  test("should not retrieve a result", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("search-bar").fill("test");

    const results = await page.locator("data-testid=results-container");

    await expect(results).toBeVisible();

    const result = await results.getByText("No results found");

    await expect(result).toBeVisible();
  });

  test("should retrieve a result", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("search-bar").fill(OBJECT_SEARCH);

    const results = await page.getByTestId("results-container");

    await expect(results).toBeVisible();

    const result = await page.getByTestId("results-container").getByText(OBJECT_SEARCH).first();

    await expect(result).toBeVisible();
  });
});
