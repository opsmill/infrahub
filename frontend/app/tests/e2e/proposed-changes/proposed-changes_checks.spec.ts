import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("/proposed-changes checks", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should display checks on a proposed change", async ({ page }) => {
    await page.goto("/proposed-changes/new");

    await test.step("create a new proposed change", async () => {
      await expect(page.getByRole("heading", { name: "Create a proposed change" })).toBeVisible();
      await page.getByLabel("Name *").fill("pc-checks");
      await page.getByLabel("Source Branch *").click();
      await page.getByRole("option", { name: "atl1-delete-upstream" }).click();
      await page.getByRole("button", { name: "Open" }).click();
      await expect(page.getByText("Proposed change created")).toBeVisible();
    });

    await test.step("go to Checks tab and see summary for all checks", async () => {
      await page.getByLabel("Tabs").getByText("Checks").click();
      if (process.env.UPDATE_DOCS_SCREENSHOTS) {
        await expect(page.getByTestId("checks-summary")).toBeVisible();
        while (
          (await page.getByText("Data Integrity").isHidden()) ||
          (await page.getByText("Schema Integrity").isHidden())
        ) {
          // checks are async, we must wait for them
          await page.reload();
          await expect(page.getByLabel("Tabs").getByText("Checks")).toBeVisible();
          await expect(page.getByTestId("checks-summary")).toBeVisible();
        }
      }
      const checksSummary = page.getByTestId("checks-summary");
      await expect(checksSummary.getByText("Retry")).toBeVisible();
      await expect(checksSummary.getByText("Artifact")).toBeVisible();
      await expect(checksSummary.getByText("Data")).toBeVisible();
      await expect(checksSummary.getByText("Generator")).toBeVisible();
      await expect(checksSummary.getByText("Repository")).toBeVisible();
      await expect(checksSummary.getByText("Schema")).toBeVisible();
      await expect(checksSummary.getByText("User")).toBeVisible();
      await expect(page.url()).toContain("tab=checks");

      await page.waitForTimeout(3000); // wait for circle animation to finish
      await saveScreenshotForDocs(page, "topics/proposed_change/pc_tab_checks");
    });
  });

  test("should delete proposed changes", async ({ page }) => {
    await page.goto("/proposed-changes");
    await page.getByTestId("actions-row-button-pc-checks").click();
    await page.getByTestId("delete-row-button").click();
    await expect(page.getByTestId("modal-delete")).toBeVisible();
    await page.getByTestId("modal-delete-confirm").click();
    await expect(page.getByText("Proposed changes pc-checks deleted")).toBeVisible();
  });
});
