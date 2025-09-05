import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { deleteBranchAPI } from "../utils/graphql";

test.describe("Verify branch merge button state", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("merge-action-test");

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("create a branch, merge it and verify button state", async ({ page }) => {
    await test.step("Create and access a new branch", async () => {
      await page.goto("/branches");
      await page.getByTestId("branch-selector-trigger").click();
      await page.getByTestId("create-branch-button").click();
      await page.getByRole("textbox", { name: "New branch name *" }).fill(BRANCH_NAME);
      await page.getByRole("button", { name: "Create a new branch" }).click();
      await expect(page.getByText("New branch name *")).not.toBeVisible();
      await expect(page.getByTestId("branches-items").getByText(BRANCH_NAME)).toBeVisible();
      await page.getByTestId("branches-items").getByText(BRANCH_NAME).click();
      await expect(page.getByText(`Name${BRANCH_NAME}`)).toBeVisible();
      await page.getByText("Tasks").click();
    });

    await test.step("Merge the branch and verify button state", async () => {
      test.slow();

      await page.getByRole("button", { name: "Merge", exact: true }).click();
      await expect(page.getByText("Branch merge requested!")).toBeVisible();
      await expect(page.getByText("RUNNINGMerge branch graphQL")).toBeVisible();
      await expect(page.getByRole("button", { name: "Merge", exact: true })).toBeDisabled();
      await expect(page.getByText("COMPLETEDMerge branch graphQL")).toBeVisible();
      await expect(page.getByRole("button", { name: "Merge", exact: true })).toBeEnabled();
    });
  });
});
