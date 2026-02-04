import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Branch details view", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.describe("default branch", () => {
    test("should display branch name and default badge", async ({ page }) => {
      await page.goto("/branches/main");

      // Header
      await expect(page.getByRole("heading", { name: "main" })).toBeVisible();
      await expect(page.getByText("default", { exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "View node metadata" })).toBeVisible();

      // Tabs
      await expect(page.getByRole("navigation", { name: "Tabs" })).not.toBeVisible();

      // Branch attributes
      await expect(page.getByText("Name")).toBeVisible();
      await expect(page.getByText("Sync with Git")).toBeVisible();

      // Non-default specific attributes should NOT be visible
      await expect(page.getByText("Has schema changes")).not.toBeVisible();
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
      await expect(page.getByText("Has schema changes")).toBeVisible();
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
      // Click on Data tab
      await tabsNav.getByText("Data").click();
      await expect(page).toHaveURL(/.*branch_tab=data/);

      // Click on Files tab
      await tabsNav.getByText("Files").click();
      await expect(page).toHaveURL(/.*branch_tab=files/);

      // Click on Artifacts tab
      await tabsNav.getByText("Artifacts").click();
      await expect(page).toHaveURL(/.*branch_tab=artifacts/);

      // Click on Schema tab
      await tabsNav.getByText("Schema").click();
      await expect(page).toHaveURL(/.*branch_tab=schema/);

      // Go back to Details tab (first tab clears the QSP)
      await tabsNav.getByText("Details").click();
      // First tab doesn't set QSP, so URL should not contain branch_tab
      await expect(page).not.toHaveURL(/.*branch_tab=details/);
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
});
