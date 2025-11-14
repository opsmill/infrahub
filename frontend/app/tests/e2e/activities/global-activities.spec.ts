import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("Global Activities - List view and filter usage", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should navigate to global activity log from sidebar", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("sidebar").getByRole("button", { name: "Activity" }).click();
    await page.getByRole("menuitem", { name: "Activities" }).click();
    await expect(page.getByRole("heading", { name: "Activities" })).toBeVisible();
  });

  test("should filter activities by primary node tag", async ({ page }) => {
    await test.step("Navigate to activity log page", async () => {
      await page.goto("/activities");
    });

    await test.step("Apply primary node filter for blue tag", async () => {
      await page.getByRole("button", { name: "Primary Node" }).click();
      await page.getByPlaceholder("Filter...").fill("tag");
      await page.getByRole("option", { name: "Tag", exact: true }).click();
      await page.getByRole("option", { name: "blue" }).click();
      await page.getByRole("button", { name: "Apply" }).click();

      await expect(page.getByRole("button", { name: "Primary Node blue" })).toBeVisible();
      await saveScreenshotForDocs(page, "topics/activity-logs/activity_log_global_filters_primary");
    });
  });

  test("should filter activities by has children and view event details with children", async ({
    page,
  }) => {
    await test.step("Navigate to activity log page", async () => {
      await page.goto("/activities");
      await expect(page.getByRole("heading", { name: "Activities" })).toBeVisible();
    });

    await test.step("Apply has children filter set to true", async () => {
      await page.getByRole("button", { name: "Has Children" }).click();
      await page.getByText("True").click();
      await page.getByRole("button", { name: "Apply" }).click();
      await expect(page.getByRole("button", { name: "Has Children true" })).toBeVisible();
      await saveScreenshotForDocs(
        page,
        "topics/activity-logs/activity_log_global_filters_children"
      );
    });

    await test.step("Open event details and verify children are displayed", async () => {
      await page.getByRole("link", { name: "View details" }).first().click();

      while (await page.getByText("No activity found for this object.").isVisible()) {
        await page.reload();
        await expect(page.getByTestId("activities-container").getByText("Loading...")).toBeHidden();
      }
      // Check that at least one "View more." button is present in the details page
      await expect(page.getByRole("button", { name: "View more" }).first()).toBeVisible();
      await saveScreenshotForDocs(
        page,
        "topics/activity-logs/activity_log_global_details_children"
      );
    });
  });
});
