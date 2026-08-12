import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI } from "../utils/graphql";

test.describe("Branch details view", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.describe("default branch", () => {
    test("should display branch name and default badge", async ({ page }) => {
      await page.goto("/branches/main");

      // Header
      await expect(page.getByRole("heading", { name: "main" })).toBeVisible();
      await expect(page.getByText("default", { exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "View node metadata" })).toBeVisible();

      // Already working on main, so there is nothing to switch to
      await expect(page.getByTestId("branch-working-notice")).toBeVisible();
      await expect(page.getByTestId("switch-to-viewed-branch")).not.toBeVisible();

      // Tabs
      await expect(page.getByRole("navigation", { name: "Tabs" })).not.toBeVisible();

      // Branch attributes
      await expect(page.getByText("Name")).toBeVisible();
      await expect(page.getByText("Sync with Git")).toBeVisible();

      // Non-default specific attributes should NOT be visible
      await expect(page.getByText("Schema differs from default branch")).not.toBeVisible();
      await expect(page.getByText("Last rebase")).not.toBeVisible();

      // All action buttons should be not visible
      await expect(page.getByRole("button", { name: "Merge" })).not.toBeVisible();
      await expect(page.getByRole("button", { name: "Rebase" })).not.toBeVisible();
      await expect(page.getByRole("button", { name: "Validate" })).not.toBeVisible();
      await expect(page.getByRole("button", { name: "Delete" })).not.toBeVisible();
      await expect(page.getByRole("button", { name: "Rebase" })).not.toBeVisible();
      await expect(page.getByRole("link", { name: "Propose change" })).not.toBeVisible();
      await expect(page.getByTestId("tasks-accordion")).not.toBeVisible();
    });
  });

  test.describe("non-default branch", () => {
    const BRANCH_NAME = "atl1-delete-upstream";

    test("should display branch name and no default badge", async ({ page }) => {
      await page.goto(`/branches/${BRANCH_NAME}`);

      // Header
      await expect(page.getByRole("heading", { name: BRANCH_NAME })).toBeVisible();
      await expect(page.getByText("default")).not.toBeVisible();
      await expect(page.getByRole("button", { name: "View node metadata" })).toBeVisible();

      // Branch attributes
      await expect(page.getByText("Name")).toBeVisible();
      await expect(page.getByText("Sync with Git")).toBeVisible();
      await expect(page.getByText("Schema differs from default branch")).toBeVisible();
      await expect(page.getByText("Last rebase")).toBeVisible();

      // Tabs navigation should be visible
      const tabsNav = page.getByRole("navigation", { name: "Tabs" });
      await expect(tabsNav).toBeVisible();

      // All tabs should be visible
      await expect(tabsNav.getByText("Details")).toBeVisible();
      await expect(tabsNav.getByText("Data")).toBeVisible();
      await expect(tabsNav.getByText("Files")).toBeVisible();
      await expect(tabsNav.getByText("Artifacts")).toBeVisible();
      await expect(tabsNav.getByText("Schema")).toBeVisible();

      // All action buttons should be visible and enabled
      await expect(page.getByRole("button", { name: "Merge" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Propose change" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Rebase" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Validate" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Delete", exact: true })).toBeVisible();
      await expect(page.getByTestId("tasks-accordion")).toBeVisible();
    });

    test("should navigate between tabs", async ({ page }) => {
      await page.goto(`/branches/${BRANCH_NAME}`);

      const tabsNav = page.getByRole("navigation", { name: "Tabs" });

      await tabsNav.getByText("Data").click();
      await expect(page).toHaveURL(new RegExp(`/branches/${BRANCH_NAME}/data`));

      await tabsNav.getByText("Files").click();
      await expect(page).toHaveURL(new RegExp(`/branches/${BRANCH_NAME}/files`));

      await tabsNav.getByText("Artifacts").click();
      await expect(page).toHaveURL(new RegExp(`/branches/${BRANCH_NAME}/artifacts`));

      await tabsNav.getByText("Schema").click();
      await expect(page).toHaveURL(new RegExp(`/branches/${BRANCH_NAME}/schema`));

      await tabsNav.getByText("Details").click();
      await expect(page).toHaveURL(new RegExp(`/branches/${BRANCH_NAME}$`));
    });

    test("should switch to the viewed branch from the mismatch notice", async ({ page }) => {
      await page.goto(`/branches/${BRANCH_NAME}`);

      await expect(page.getByTestId("branch-mismatch-notice")).toContainText(
        `You're viewing ${BRANCH_NAME} but working on main`
      );

      await page.getByTestId("switch-to-viewed-branch").click();

      await expect(page.getByTestId("branch-working-notice")).toBeVisible();
      await expect(page.getByTestId("branch-mismatch-notice")).not.toBeVisible();
      await expect(page.getByTestId("branch-selector-trigger")).toContainText(BRANCH_NAME);
    });

    test("should display node metadata when clicking metadata button", async ({ page }) => {
      await page.goto(`/branches/${BRANCH_NAME}`);

      await page.getByRole("button", { name: "View node metadata" }).click();

      await expect(page.getByText("Created at")).toBeVisible();
      await expect(page.getByText("Created by")).toBeVisible();
      await expect(page.getByText("Updated at")).toBeVisible();
      await expect(page.getByText("Updated by")).toBeVisible();
    });
  });

  test.describe("branch name containing a slash", () => {
    test("opens the detail page from the branches list", async ({ page, request }) => {
      const branchName = generateRandomBranchName("playwright/slash-");
      await createBranchAPI(request, branchName);

      await page.goto("/branches");
      await page.getByRole("link", { name: branchName, exact: true }).click();

      await expect(page.getByRole("heading", { name: branchName })).toBeVisible();
      await expect(page.getByRole("navigation", { name: "Tabs" })).toBeVisible();
      await expect(page).toHaveURL(
        (url) => url.pathname === `/branches/${encodeURIComponent(branchName)}`
      );
    });

    test("navigates to a path-based tab", async ({ page, request }) => {
      const branchName = generateRandomBranchName("playwright/slash-");
      await createBranchAPI(request, branchName);

      await page.goto(`/branches/${encodeURIComponent(branchName)}`);

      await page.getByRole("navigation", { name: "Tabs" }).getByText("Data").click();

      await expect(page.getByRole("heading", { name: branchName })).toBeVisible();
      await expect(page).toHaveURL(
        (url) => url.pathname === `/branches/${encodeURIComponent(branchName)}/data`
      );
    });
  });
});
