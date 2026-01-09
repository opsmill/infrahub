import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { createBranch, generateRandomBranchName } from "../../utils";

test.describe("Branches creation and deletion", () => {
  test.describe("when not logged in", () => {
    test("should not be able to create a branch if not logged in", async ({ page }) => {
      await page.goto("/");
      await page.getByTestId("branch-selector-trigger").click();
      await expect(page.getByTestId("create-branch-button")).toBeDisabled();
    });

    test("should not show quick-create option when searching for non-existent branch", async ({
      page,
    }) => {
      await page.goto("/");
      await page.getByTestId("branch-selector-trigger").click();

      const nonExistentBranchName = "non-existent-branch-123";
      await page.getByTestId("branch-search-input").fill(nonExistentBranchName);

      await expect(page.getByText("No branch found")).toBeVisible();
      await expect(
        page.getByRole("option", { name: `Create branch ${nonExistentBranchName}` })
      ).not.toBeVisible();
    });
  });

  test.describe("when logged in as Admin", () => {
    test.describe.configure({ mode: "serial" });
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    const BRANCH_NAME_1 = generateRandomBranchName();
    const BRANCH_NAME_2 = generateRandomBranchName();

    test("should create a new branch", async ({ page }) => {
      await page.goto("/");
      await page.getByTestId("branch-selector-trigger").click();
      await page.getByTestId("create-branch-button").click();

      // Form
      await expect(page.getByText("Create a new branch")).toBeVisible();
      await page.getByLabel("New branch name *").fill(BRANCH_NAME_1);
      await page.getByText("New branch description").fill("branch creation test");
      await page.getByRole("button", { name: "Create a new branch" }).click();

      // After submit
      await expect(page.getByTestId("branch-selector-trigger")).toContainText(BRANCH_NAME_1);
      await expect(page).toHaveURL(new RegExp(`.*?branch=${BRANCH_NAME_1}`));
    });

    test("should display the new branch", async ({ page }) => {
      await page.goto("/");
      await page.getByTestId("branch-selector-trigger").click();
      await expect(page.getByTestId("branch-list")).toContainText(BRANCH_NAME_1);

      await page.getByRole("link", { name: "View all branches" }).click();
      await expect(page).toHaveURL(/.*\/branches/);

      await page.getByText(BRANCH_NAME_1).click();
      await expect(page.getByText(`Name${BRANCH_NAME_1}`)).toBeVisible();

      await page.getByRole("button", { name: "View node metadata" }).click();
      await expect(page.getByText("Created at")).toBeVisible();
      await expect(page.getByText("Created by")).toBeVisible();
      await expect(page.getByText("Updated at")).toBeVisible();
      await expect(page.getByText("Updated by")).toBeVisible();

      expect(page.url()).toContain(`/branches/${BRANCH_NAME_1}`);
    });

    test("create a new branch for next step", async ({ page }) => {
      await page.goto("/");
      await createBranch(page, BRANCH_NAME_2);
    });

    test("should delete a non-selected branch and remain on the current branch", async ({
      page,
    }) => {
      await page.goto(`/branches/${BRANCH_NAME_2}?branch=${BRANCH_NAME_1}`);

      await page.getByRole("button", { name: "Delete" }).click();

      const modalDelete = page.getByTestId("modal-delete");
      await expect(modalDelete.getByRole("heading", { name: "Delete" })).toBeVisible();
      await expect(
        modalDelete.getByText(`Are you sure you want to remove the branch \`${BRANCH_NAME_2}\`?`)
      ).toBeVisible();
      await modalDelete.getByRole("button", { name: "Delete" }).click();

      // we should stay on the branch
      await expect(page.getByTestId("branch-selector-trigger")).toContainText(BRANCH_NAME_1);
      await page.getByTestId("branch-selector-trigger").click();
      await expect(page.getByTestId("branch-list")).toContainText(BRANCH_NAME_1);
      await expect(page.getByTestId("branch-list")).not.toContainText(BRANCH_NAME_2);
      await expect(page.getByRole("heading", { name: "Branches" })).toBeVisible();
      expect(page.url()).toContain(`/branches?branch=${BRANCH_NAME_1}`);
    });

    test("should delete the currently selected branch", async ({ page }) => {
      await page.goto("/branches");
      await page.getByText(BRANCH_NAME_1).click();
      await page.getByRole("button", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();

      await expect(page.getByRole("heading", { name: "Branches" })).toBeVisible();
      expect(page.url()).toContain("/branches");
      await page.getByTestId("branch-selector-trigger").click();
      await expect(page.getByTestId("branch-list")).not.toContainText(BRANCH_NAME_1);
    });

    test("allow to create a branch with a name that does not exists", async ({ page }) => {
      await page.goto("/");
      await page.getByTestId("branch-selector-trigger").click();
      await page.getByTestId("branch-search-input").fill("quick-branch-form");
      await page.getByRole("option", { name: "Create branch quick-branch-form" }).click();
      await expect(page.getByLabel("New branch name *")).toHaveValue("quick-branch-form");
    });

    test("verify if the current branch exists correctly and redirects to home on main branch", async ({
      page,
    }) => {
      await page.goto("/");
      await expect(page.getByRole("button", { name: "Other" })).toBeVisible();
      await page.goto("/?branch=unknown-branch-for-testing");
      expect(page.url()).toContain("/?branch=unknown-branch-for-testing");
      await expect(page.getByText("you have been redirected to the main branch")).toBeVisible();
      await expect(page.getByRole("button", { name: "Other" })).toBeVisible();
      expect(page.url()).not.toContain("/?branch=unknown-branch-for-testing");
    });

    test("should search for a branch", async ({ page }) => {
      await page.goto("/branches");
      await expect(page.getByRole("link", { name: "main", exact: true })).toBeVisible();
      await expect(page.getByRole("link", { name: "den1-maintenance-conflict" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-delete-upstream" })).toBeVisible();
      await page.getByRole("searchbox", { name: "Search" }).fill("main");
      await expect(page.getByRole("link", { name: "main", exact: true })).toBeVisible();
      await expect(page.getByRole("link", { name: "den1-maintenance-conflict" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-delete-upstream" })).not.toBeVisible();

      await page.getByRole("searchbox", { name: "Search" }).fill("");
      await expect(page.getByRole("link", { name: "atl1-delete-upstream" })).toBeVisible();
    });
  });
});
