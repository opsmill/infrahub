import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("Global Activity Log - List view and filter usage", () => {
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

  test("1. Reach global activity-log", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("sidebar").getByRole("button", { name: "Activity" }).click();
    await page.getByRole("menuitem", { name: "Activities" }).click();
    // Verify that clicking "Activity Log" navigates to the activities page
    const activitiesHeading = page.getByRole("heading", { name: "Activities" });
    await expect(activitiesHeading).toBeVisible();
  });

  test("2. View the Activity log page", async ({ page }) => {
    await test.step("Go to activity log page", async () => {
      await page.goto("/activities");
    });

    await test.step("Choose filters", async () => {
      await page.getByRole("button", { name: "Primary Node" }).click();

      // Narrow the search to the dialog that contains the "Primary Node" text.
      await page.getByPlaceholder("Filter...").fill("blue");
      await page.getByRole("option", { name: "blue" }).click();

      await expect(page.getByText("blue")).toBeVisible();
      await saveScreenshotForDocs(page, "activity_log_global_filters_primary");
    });
  });
  test("3. View the Activity log page with children", async ({ page }) => {
    await test.step("Go to activity log page", async () => {
      await page.goto("/activities");
      const activitiesHeading = page.getByRole("heading", { name: "Activities" });
      await expect(activitiesHeading).toBeVisible();
    });

    await test.step("Choose filters", async () => {
      await page.getByRole("button", { name: "Has Children" }).click();
      await page.getByText("True").click();
      await page.getByRole("button", { name: "Apply" }).click();
      await saveScreenshotForDocs(page, "activity_log_global_filters_children");
    });

    await test.step("View Event details with children", async () => {
      const viewMoreLink = page.getByRole("link", { name: /View more/i }).first();
      await viewMoreLink.click();

      // Check that at least one "View more." button is present in the details page
      await expect(page.locator("#root")).toContainText("View more.");
      await saveScreenshotForDocs(page, "activity_log_global_details_children");
    });
  });
});
