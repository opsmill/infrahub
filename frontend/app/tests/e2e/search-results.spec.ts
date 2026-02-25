import { expect, test } from "@playwright/test";

test.describe("search results page", () => {
  test("navigates from search anywhere dropdown to full results page", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere and type a query", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
      await page.getByTestId("search-anywhere-input").fill("atl");
    });

    await test.step("verify View all results link is visible", async () => {
      await expect(page.getByRole("link", { name: /View all \d+ results?/ })).toBeVisible();
    });

    await test.step("click View all results link", async () => {
      await page.getByRole("link", { name: /View all \d+ results?/ }).click();
      await expect(page).toHaveURL(/\/search\?q=atl/);
    });

    await test.step("verify search results page loads with results", async () => {
      await expect(page.getByTestId("search-results-input")).toHaveValue("atl");
      await expect(page.getByText(/\d+ results?/)).toBeVisible();
    });
  });

  test("loads search results page directly via URL", async ({ page }) => {
    await page.goto("/search?q=atl");

    await test.step("verify search input is pre-filled", async () => {
      await expect(page.getByTestId("search-results-input")).toHaveValue("atl");
    });

    await test.step("verify results are displayed", async () => {
      await expect(page.getByText(/\d+ results?/)).toBeVisible();
    });
  });

  test("shows empty state for no results", async ({ page }) => {
    await page.goto("/search?q=zzz_no_results_xyz_12345");

    await test.step("verify no results message", async () => {
      await expect(page.getByText("No results found")).toBeVisible();
    });
  });

  test("allows editing search query on results page", async ({ page }) => {
    await page.goto("/search?q=atl");

    await test.step("change search query", async () => {
      const input = page.getByTestId("search-results-input");
      await input.clear();
      await input.fill("devi");
      await input.press("Enter");
    });

    await test.step("verify URL updated", async () => {
      await expect(page).toHaveURL(/\/search\?q=devi/);
    });
  });
});
