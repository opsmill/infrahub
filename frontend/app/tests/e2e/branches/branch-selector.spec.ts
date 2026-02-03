import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Branch selector", () => {
  test.describe("when not logged in", () => {
    test("should not be able to create a branch if not logged in", async ({ page }) => {
      await page.goto("/");
      await page.getByTestId("branch-selector-trigger").click();
      await expect(page.getByTestId("create-branch-button")).toBeDisabled();

      await test.step("to go branch list view", async () => {
        await page.getByRole("link", { name: "View all branches" }).click();
        await expect(page.getByTestId("branches-table")).toContainText("main");
      });
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

    test("should be able to search and switch branch", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByTestId("branch-selector-trigger")).toContainText("main");
      await page.getByTestId("branch-selector-trigger").click();
      await expect(
        page.getByTestId("branch-list").getByRole("option", { name: "main default" })
      ).toBeVisible();

      await page.getByTestId("branch-search-input").fill("atl1");
      await expect(
        page.getByTestId("branch-list").getByRole("option", { name: "atl1-delete-upstream" })
      ).toBeVisible();
      await expect(page.getByTestId("branch-list").getByRole("option")).toHaveCount(1);
      await page
        .getByTestId("branch-list")
        .getByRole("option", { name: "atl1-delete-upstream" })
        .click();
      await expect(page.getByTestId("branch-selector-trigger")).toContainText(
        "atl1-delete-upstream"
      );
      expect(page.url()).toContain("/?branch=atl1-delete-upstream");
    });
  });

  test.describe("when logged in as Admin", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

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
      await page.goto("/?branch=unknown-branch-for-testing");
      await expect(page.getByText("you have been redirected to the main branch")).toBeVisible();
      await expect(page.getByRole("button", { name: "Other" })).toBeVisible();
      expect(page.url()).not.toContain("/?branch=unknown-branch-for-testing");
    });
  });
});
