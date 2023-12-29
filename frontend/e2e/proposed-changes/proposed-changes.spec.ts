import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../tests/utils";

test.describe("/proposed-changes", () => {
  test.describe("when not logged in", () => {
    test("should not be able to create a proposed changes", async ({ page }) => {
      await page.goto("/proposed-changes");

      await expect(page.getByText("ProposedChange")).toBeVisible();
      await expect(page.getByTestId("add-proposed-changes-button")).toBeDisabled();
    });
  });

  test.describe("when logged in as Admin", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should be able to create a proposed changes", async ({ page }) => {
      await page.goto("/proposed-changes");

      await expect(page.getByText("ProposedChange")).toBeVisible();
      await expect(page.getByTestId("add-proposed-changes-button")).toBeEnabled();
      await page.getByTestId("add-proposed-changes-button").click();
      await expect(page.getByText("Create Proposed Changes")).toBeVisible();
    });
  });
});
