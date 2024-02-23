import { expect, test } from "@playwright/test";

test.describe("when searching an object", () => {
  test("should open search anywhere modal", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere modal with click", async () => {
      await page.getByPlaceholder("Search anywhere").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    await test.step("close search anywhere modal with esc key", async () => {
      await page.locator("body").press("Escape");
      await expect(page.getByTestId("search-anywhere")).not.toBeVisible();
    });

    await test.step("open search anywhere modal when typing on header input", async () => {
      await page.getByPlaceholder("Search anywhere").fill("e");
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });
  });

  test("should display message when no results found", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere modal", async () => {
      await page.getByPlaceholder("Search anywhere").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    await test.step("find a matching result", async () => {
      await page.getByTestId("search-anywhere").getByPlaceholder("Search anywhere").fill("atl1");
      await expect(
        page.getByTestId("search-anywhere").getByRole("option", { name: "atl1Site" })
      ).toBeVisible();
    });
  });
});
