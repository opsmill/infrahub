import { expect, test } from "@playwright/test";

const OBJECT_SEARCH = "atl1-edge1";

test.describe("when searching an object", () => {
  test.fixme("should not retrieve a result", async ({ page }) => {
    await page.goto("/");

    await Promise.all([
      page.waitForResponse((response) => {
        const reqData = response.request().postDataJSON();
        const status = response.status();

        return reqData?.operationName === "CoreNode" && status === 200;
      }),

      page.getByTestId("search-bar").fill("test"),
    ]);

    const results = page.getByTestId("results-container");

    await expect(results).toBeVisible();

    const result = await results.getByText("No results found");

    await expect(result).toBeVisible();
  });

  test.fixme("should retrieve a result", async ({ page }) => {
    await page.goto("/");

    await Promise.all([
      page.waitForResponse((response) => {
        const reqData = response.request().postDataJSON();
        const status = response.status();

        return reqData?.operationName === "CoreNode" && status === 200;
      }),

      page.getByTestId("search-bar").fill(OBJECT_SEARCH),
    ]);

    const results = page.getByTestId("results-container");

    await expect(results).toBeVisible();

    const result = await page.getByTestId("results-container").getByText(OBJECT_SEARCH).first();

    await expect(result).toBeVisible();
  });
});
