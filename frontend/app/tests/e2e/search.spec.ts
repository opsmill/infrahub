import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../constants";

test.describe("when searching an object", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should open search anywhere modal", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere modal with click", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    await test.step("close search anywhere modal with esc key", async () => {
      await page.locator("body").press("Escape");
      await expect(page.getByTestId("search-anywhere")).not.toBeVisible();
    });

    await test.step("open search anywhere modal when typing on header input", async () => {
      await page.keyboard.press("Enter");
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });
  });

  test("displays link to Device list", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere modal with click", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    await test.step("find a matching result", async () => {
      await page.getByTestId("search-anywhere").getByPlaceholder("Search anywhere").fill("devi");
      await expect(page.getByTestId("search-anywhere")).toContainText("Go to");
      await page.getByRole("option", { name: "Menu Device" }).click();
      await expect(page.getByRole("heading", { name: "Device" })).toBeVisible();
      expect(page.url()).toContain("/objects/InfraDevice");
    });
  });

  test("should display a message when no results found", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere modal", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    const searchAnywhere = page.getByTestId("search-anywhere");
    await test.step("open search anywhere modal when typing on header input", async () => {
      await searchAnywhere.getByPlaceholder("Search anywhere").fill("no_results_query_for_test");
      await expect(searchAnywhere.getByRole("option")).toContainText(
        "Search in docs: no_results_query_for_test"
      );
    });
  });

  test("should display results on search nodes", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere modal", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    await test.step("find a matching result", async () => {
      await page.getByTestId("search-anywhere").getByPlaceholder("Search anywhere").fill("atl1");
      await expect(
        page.getByTestId("search-anywhere").getByRole("option", { name: "atl1 Location Site" })
      ).toBeVisible();
    });
  });

  test("display result when searching by uuid", async ({ page }) => {
    await page.goto("/objects/InfraAutonomousSystem");

    await page.getByRole("link", { name: "AS174", exact: true }).click();
    const uuid = (await page.locator("dd").first().textContent()) as string;

    await test.step("open search anywhere modal", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    await page.getByTestId("search-anywhere").getByPlaceholder("Search anywhere").fill(uuid);
    await expect(
      page.getByRole("option", { name: "AS174 174 Infra Autonomous System" })
    ).toBeVisible();
  });
});
