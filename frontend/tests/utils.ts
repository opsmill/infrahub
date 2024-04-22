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
    path: `../docs/docs/media/${filename}.png`,
    animations: "disabled",
  });
};

export const createBranch = async (page: Page, branchName: string) => {
  await page.getByTestId("create-branch-button").click();
  await page.locator("[id='New branch name']").fill(branchName);

  await Promise.all([
    page.waitForResponse((response) => {
      const reqData = response.request().postDataJSON();
      const status = response.status();

      return reqData?.operationName === "BranchCreate" && status === 200;
    }),
    page.waitForURL("/?branch=" + branchName), // createBranch redirects to this URL, we must wait for it to avoid ERR_ABORTED errors in the next goto
    page.waitForResponse((response) => {
      const reqData = response.request().postDataJSON();
      const status = response.status();

      // filter the BranchCreate request that happens on the same url
      return (
        reqData?.operationName !== "BranchCreate" &&
        response.url().match(new RegExp("graphql/(main|" + branchName + ")")) != null &&
        status === 200
      );
    }),
    page.getByRole("button", { name: "Create" }).click(),
  ]); // to avoid ERR_ABORTED
};

export const deleteBranch = async (page: Page, branchName: string) => {
  await page.goto("/branches/" + branchName);
  await page.getByRole("button", { name: "Delete" }).click();
  await page.getByTestId("modal-delete-confirm").click();
};
