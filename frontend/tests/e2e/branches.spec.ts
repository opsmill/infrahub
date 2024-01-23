import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH, createBranch } from "../utils";

test.describe("Branches creation and deletion", () => {
  test.describe("when not logged in", () => {
    test("should not be able to create a branch if not logged in", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByTestId("branch-select-menu")).toContainText("main");
      await expect(page.getByTestId("create-branch-button")).toBeDisabled();
    });
  });

  test.describe("when logged in as Admin", () => {
    test.describe.configure({ mode: "serial" });
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should create a new branch", async ({ page }) => {
      await page.goto("/");
      await page.getByTestId("create-branch-button").click();

      // Form
      await expect(page.getByText("Create a new branch")).toBeVisible();
      await page.locator("[id='New branch name']").fill("test123");
      await page.locator("[id='New branch description']").fill("branch creation test");
      await page.getByRole("button", { name: "Create" }).click();

      // After submit
      await expect(page.getByTestId("branch-select-menu")).toContainText("test123");
      await expect(page).toHaveURL(/.*?branch=test123/);
    });

    test("should display the new branch", async ({ page }) => {
      await page.goto("/");
      await page.getByTestId("branch-list-display-button").click();
      await expect(page.getByTestId("branch-list-dropdown")).toContainText("test123");

      await page.getByTestId("sidebar-menu").getByText("Branches").click();
      await expect(page).toHaveURL(/.*\/branches/);

      await page.getByTestId("branches-items").getByText("test123").click();
      expect(page.url()).toContain("/branches/test123");
    });

    test("should delete a non-selected branch and remain on the current branch", async ({
      page,
    }) => {
      await page.goto("/");
      await createBranch(page, "test456");
      await page.goto("/branches/test456?branch=test123");

      await page.getByRole("button", { name: "Delete" }).click();

      const modalDelete = await page.getByTestId("modal-delete");
      await expect(modalDelete.getByRole("heading", { name: "Delete" })).toBeVisible();
      await expect(
        modalDelete.getByText("Are you sure you want to remove the branch `test456`?")
      ).toBeVisible();
      await modalDelete.getByRole("button", { name: "Delete" }).click();

      // we should stay on the branch test123
      await expect(page.getByTestId("branch-select-menu")).toContainText("test123");
      await page.getByTestId("branch-list-display-button").click();
      await expect(page.getByTestId("branch-list-dropdown")).toContainText("test123");
      await expect(page.getByTestId("branch-list-dropdown")).not.toContainText("test456");
      expect(page.url()).toContain("/branches?branch=test123");
    });

    test("should delete the currently selected branch", async ({ page }) => {
      await page.goto("/");
      await page.getByRole("link", { name: "Branches" }).click();
      await page.getByText("test123").click();
      await page.getByRole("button", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();

      expect(page.url()).toContain("/branches");
      await page.getByTestId("branch-list-display-button").click();
      await expect(page.getByTestId("branch-list-dropdown")).not.toContainText("test123");
    });
  });
});
