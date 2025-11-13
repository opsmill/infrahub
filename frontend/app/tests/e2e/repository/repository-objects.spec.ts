import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

const GIT_REPO_URL = "https://github.com/opsmill/infrahub-demo-edge.git";
const REPO_NAME = "test repository";

test.describe("Repository - Creation and objects view", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("repository-branch");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("Create repository and access objects view", async ({ page }) => {
    await page.goto("/objects/CoreGenericRepository");
    await expect(page.getByRole("link", { name: "demo-edge" })).toBeVisible();
    await page.getByTestId("create-object-button").click();
    await page.getByRole("combobox", { name: "Select an object type" }).click();
    await page.getByRole("option", { name: "Read-Only Repository Core" }).click();
    await page.getByRole("textbox", { name: "Repository location *" }).fill(GIT_REPO_URL);
    await page.getByRole("textbox", { name: "Name *" }).fill(REPO_NAME);
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByRole("link", { name: REPO_NAME })).toBeVisible();
    await page.getByRole("link", { name: REPO_NAME }).click();
    await page
      .getByRole("link")
      .filter({ hasNotText: "Group" })
      .filter({ hasText: "Objects" })
      .click();
    await expect(page.getByText("No objects found for this")).toBeVisible();
  });
});
