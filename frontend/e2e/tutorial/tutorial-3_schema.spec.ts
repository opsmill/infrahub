import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../tests/utils";

test.describe("Getting started with Infrahub - Data lineage and metadata", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("1. Visualize the active schema", async ({ page }) => {
    await page.goto("/schema");
    await expect(page.getByText("Account Token")).toBeVisible();
  });
});
