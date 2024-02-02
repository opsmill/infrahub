import { Page } from "@playwright/test";

export const waitFor = (alias, checkFn, maxRequests = 10, level = 0) => {
  if (level === maxRequests) {
    throw `${maxRequests} requests exceeded`;
  }

  return cy.wait(alias, { timeout: 10000 }).then((interception) => {
    if (!checkFn(interception)) {
      return waitFor(alias, checkFn, maxRequests, level + 1);
    }
  });
};

export const saveScreenshotForDocs = async (page: Page, filename: string) => {
  if (!process.env.UPDATE_DOCS_SCREENSHOTS) return;

  await page.waitForLoadState("networkidle");
  await page.screenshot({
    path: `../docs/media/${filename}.png`,
    animations: "disabled",
  });
};

export const createBranch = async (page: Page, branchName: string) => {
  await page.getByTestId("create-branch-button").click();
  await page.locator("[id='New branch name']").fill(branchName);
  await page.getByRole("button", { name: "Create" }).click();
};

export const deleteBranch = async (page: Page, branchName: string) => {
  await page.goto("/branches/" + branchName);
  await page.getByRole("button", { name: "Delete" }).click();
  await page.getByTestId("modal-delete-confirm").click();
};
