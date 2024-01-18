import { Page } from "@playwright/test";

type ScreenshotConfig = {
  overwrite: boolean;
  scale: boolean;
};

export const screenshotConfig: ScreenshotConfig = {
  overwrite: true,
  scale: true,
};

export const SCREENSHOT_ENV_VARIABLE = "SCREENSHOTS";

export const ADMIN_CREDENTIALS = {
  username: "admin",
  password: "infrahub",
};

export const READ_WRITE_CREDENTIALS = {
  username: "Chloe O'Brian",
  password: "Password123",
};

export const READ_ONLY_CREDENTIALS = {
  username: "Jack Bauer",
  password: "Password123",
};

export const ENG_TEAM_ONLY_CREDENTIALS = {
  username: "Engineering Team",
  password: "Password123",
};

export const ACCOUNT_STATE_PATH = {
  ADMIN: "tests/e2e/.auth/admin.json",
  READ_WRITE: "tests/e2e/.auth/read-write.json",
  READ_ONLY: "tests/e2e/.auth/read-only.json",
};

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
  await page.locator("#new-branch-name").fill(branchName);
  await page.getByRole("button", { name: "Create" }).click();
};

export const deleteBranch = async (page: Page, branchName: string) => {
  await page.goto("/branches/" + branchName);
  await page.getByRole("button", { name: "Delete" }).click();
  await page.getByTestId("modal-delete-confirm").click();
};
