import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("Branch - Merge action", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("merge-branch");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("disable merge button during merge and re-enable when complete", async ({ page }) => {
    await test.step("access the branch details page", async () => {
      await page.goto(`/branches/${BRANCH_NAME}`);
      await page.getByText("Tasks").click();
    });

    await test.step("Merge the branch and verify button state", async () => {
      await page.getByRole("button", { name: "Merge", exact: true }).click();
      await expect(page.getByText("Branch merge requested!")).toBeVisible();
      await expect(page.getByText("RUNNINGMerge branch graphQL")).toBeVisible({
        timeout: 5 * 60 * 1000,
      });
      await expect(page.getByRole("button", { name: "Merge", exact: true })).toBeDisabled();
      await expect(page.getByText("COMPLETEDMerge branch graphQL")).toBeVisible({
        timeout: 5 * 60 * 1000,
      });
      await expect(page.getByRole("button", { name: "Merge", exact: true })).toBeEnabled();
    });
  });
});
