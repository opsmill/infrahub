import { Page, expect } from "@playwright/test";

export const saveScreenshotForDocs = async (page: Page, filename: string) => {
  if (!process.env.UPDATE_DOCS_SCREENSHOTS) return;

  await page.waitForLoadState("networkidle");
  await page.screenshot({
    path: `../../docs/docs/media/${filename}.png`,
    animations: "disabled",
  });
};

export const createBranch = async (page: Page, branchName: string) => {
  await page.getByTestId("branch-selector-trigger").click();
  await page.getByTestId("create-branch-button").click();
  await page.getByLabel("New branch name *").fill(branchName);
  await page.getByRole("button", { name: "Create a new branch" }).click();
  await expect(page.getByTestId("branch-selector-trigger")).toContainText(branchName);
};

export const deleteBranch = async (page: Page, branchName: string) => {
  await page.goto("/branches/" + branchName);
  await page.getByRole("button", { name: "Delete" }).click();
  await page.getByTestId("modal-delete-confirm").click();
};
