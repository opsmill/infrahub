import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";

test.describe("Object list search", async () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("verify the search", async ({ page }) => {
    await page.goto("/objects/InfraDevice");

    await test.step("initial state", async () => {
      await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
    });

    await test.step("should search an object and verify the total amount of results", async () => {
      await page.getByPlaceholder("Search Device").fill("core1");

      await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-edge1" })).not.toBeVisible();
    });
  });
});
