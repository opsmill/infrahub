import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH, saveScreenshotForDocs } from "../../utils";

test.describe("Getting started with Infrahub - Data lineage and metadata", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("1. Visualize the active schema", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("sidebar-menu").getByRole("link", { name: "Schema" }).click();
    await expect(page.getByText("Account Token")).toBeVisible();
    await saveScreenshotForDocs(page, "tutorial/tutorial-3-schema.cy.ts/tutorial_3_schema");
  });
});
