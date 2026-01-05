import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("Menu view - List view and filter usage", () => {
  test.describe.configure({ mode: "parallel" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.slow();

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("1. Reach Location Menu", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("sidebar").getByRole("button", { name: "Location" }).click();
    await page.getByRole("menu", { name: "Location" });
    await saveScreenshotForDocs(page, "location_menu");
  });
});
