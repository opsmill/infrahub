import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../constants";

test.describe("search anywhere - parent prefix lookup", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should display parent prefixes when searching for an IP address", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere modal", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    await test.step("search for an IP address and verify parent prefixes section", async () => {
      await page.getByTestId("search-anywhere-input").fill("10.0.0.2");

      // Parent Prefixes section should appear with containing prefixes
      const searchDialog = page.getByTestId("search-anywhere");
      await expect(searchDialog.getByText("Parent Prefixes")).toBeVisible();
      await expect(
        searchDialog.getByRole("option", { name: /10\.0\.0\.0\/16.*IP Prefix/ })
      ).toBeVisible();
      await expect(
        searchDialog.getByRole("option", { name: /10\.0\.0\.0\/8.*IP Prefix/ })
      ).toBeVisible();
    });

    await test.step("verify existing IP address appears in Objects section", async () => {
      const searchDialog = page.getByTestId("search-anywhere");
      await expect(searchDialog.getByText("Objects")).toBeVisible();
    });
  });

  test("should not display parent prefixes for non-IP search", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere and search for text", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await page.getByTestId("search-anywhere-input").fill("atl1");

      const searchDialog = page.getByTestId("search-anywhere");
      await expect(searchDialog.getByText("Objects")).toBeVisible();
      // Parent Prefixes section should NOT appear for non-IP queries
      await expect(searchDialog.getByText("Parent Prefixes")).not.toBeVisible();
    });
  });

  test("should navigate to prefix detail page when clicking a parent prefix result", async ({
    page,
  }) => {
    await page.goto("/");

    await test.step("open search and find parent prefixes", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await page.getByTestId("search-anywhere-input").fill("10.0.0.2");

      const searchDialog = page.getByTestId("search-anywhere");
      await expect(searchDialog.getByText("Parent Prefixes")).toBeVisible();
    });

    await test.step("click a parent prefix result and verify navigation", async () => {
      await page
        .getByTestId("search-anywhere")
        .getByRole("option", { name: /10\.0\.0\.0\/16.*IP Prefix/ })
        .click();

      await expect(page.getByRole("heading", { name: "10.0.0.0/16" })).toBeVisible();
      expect(page.url()).toContain("/ipam");
    });
  });
});
