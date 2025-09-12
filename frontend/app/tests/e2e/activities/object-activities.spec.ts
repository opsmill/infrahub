import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("Object Activities - Timeline and Details", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.slow();

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("1. Display the activity log details for atl1-edge1", async ({ page }) => {
    await test.step("Navigate to InfraDevice page", async () => {
      await page.goto("/objects/InfraDevice");
      await page.getByRole("link", { name: "atl1-edge1" }).click();

      while (await page.getByText("No activity found for this").isVisible()) {
        await page.reload();
        await expect(page.getByTestId("activities-container").getByText("Loading...")).toBeHidden();
      }

      await saveScreenshotForDocs(page, "topics/activity-logs/activity_log_device");
    });

    await test.step("Open additional details via the 'View more' button", async () => {
      const viewMoreButton = page.getByRole("button", { name: "View more" }).first();
      await expect(viewMoreButton).toBeVisible();
      await viewMoreButton.click();

      const popoverContent = page.getByRole("dialog");
      // Assert that the popover contains the expected text "Primary Node"
      await expect(popoverContent).toContainText("Primary Node");
      // To be sure we load the data, checking if we do have a link to the device
      await popoverContent.getByRole("link", { name: "atl1-edge1" }).waitFor({ state: "visible" });
      await saveScreenshotForDocs(page, "topics/activity-logs/activity_log_device_popover");
    });
  });
});
