import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Verify branch merge button state", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("create a branch, merge it and verify button state", async ({ page }) => {
    await test.step("Create and access a new branch", async () => {
      await page.goto("/branches");
      await page.getByTestId("branch-selector-trigger").click();
      await page.getByTestId("create-branch-button").click();
      await page.getByRole("textbox", { name: "New branch name *" }).fill("merge-action-test");
      await page.getByRole("textbox", { name: "New branch name *" }).press("Enter");
      await page.getByRole("button", { name: "Create a new branch" }).click();
      await expect(page.getByTestId("branches-items").getByText("merge-action-test")).toBeVisible();
      await page.getByTestId("branches-items").getByText("merge-action-test").click();
      await expect(page.getByText("Namemerge-action-test")).toBeVisible();
      await page.getByText("Tasks").click();
    });

    await test.step("Merge the branch and verify button state", async () => {
      await page.getByRole("button", { name: "Merge", exact: true }).click();
      await expect(page.getByText("Branch merge requested!")).toBeVisible();
      await expect(page.getByText("RUNNINGMerge branch graphQL")).toBeVisible();
      await expect(page.getByRole("button", { name: "Merge", exact: true })).toBeDisabled();
      await expect(page.getByText("COMPLETEDMerge branch graphQL")).toBeVisible();
      await expect(page.getByRole("button", { name: "Merge", exact: true })).toBeEnabled();
    });
  });
});
