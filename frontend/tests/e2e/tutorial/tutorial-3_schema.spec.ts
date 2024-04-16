import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("Getting started with Infrahub - Data lineage and metadata", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("1. Visualize the active schema", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("sidebar-menu").getByRole("link", { name: "Schema" }).click();
    await expect(page.getByText("Artifact Check")).toBeVisible();
    await saveScreenshotForDocs(page, "tutorial_3_schema");
  });
});
