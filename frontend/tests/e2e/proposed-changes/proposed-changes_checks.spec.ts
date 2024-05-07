import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/proposed-changes checks", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should display checks on a proposed change", async ({ page }) => {
    await page.goto("/proposed-changes");

    await test.step("create a new proposed change", async () => {
      await page.getByTestId("add-proposed-changes-button").click();
      await expect(page.getByText("Create Proposed Change")).toBeVisible();
      await page.getByLabel("Name *").fill("pc-checks");
      await page
        .getByText("Source Branch")
        .locator("../..")
        .getByTestId("select-open-option-button")
        .click();
      await page.getByRole("option", { name: "atl1-delete-upstream" }).click();
      await page.getByRole("button", { name: "Create" }).click();
      await expect(page.getByText("Proposed change created")).toBeVisible();
    });

    await test.step("go to Checks tab and see summary for all checks", async () => {
      await page.getByLabel("Tabs").getByText("Checks").click();
      const checksSummary = page.getByTestId("checks-summary");
      await expect(checksSummary.getByText("Retry")).toBeVisible();
      await expect(checksSummary.getByText("Artifact")).toBeVisible();
      await expect(checksSummary.getByText("Data")).toBeVisible();
      await expect(checksSummary.getByText("Generator")).toBeVisible();
      await expect(checksSummary.getByText("Repository")).toBeVisible();
      await expect(checksSummary.getByText("Schema")).toBeVisible();
      await expect(checksSummary.getByText("User")).toBeVisible();
      await expect(page.url()).toContain("pr_tab=checks");
    });
  });

  test("should delete proposed changes", async ({ page }) => {
    await page.goto("/proposed-changes");
    await page.getByText("pc-checks").first().hover();
    await page.locator("[data-testid='delete-proposed-change-button']:visible").click();
    await expect(page.getByTestId("modal-delete")).toBeVisible();
    await page.getByTestId("modal-delete-confirm").click();
    await expect(page.getByText("Proposed changes deleted")).toBeVisible();
  });
});
