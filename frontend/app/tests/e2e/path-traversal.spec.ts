import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../constants";

test.describe("/path-traversal", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should load page with Path Traversal heading", async ({ page }) => {
    await page.goto("/path-traversal");

    await expect(page.getByText("Path Traversal")).toBeVisible();
  });

  test("should display mode toggle with Path and Dependencies buttons", async ({ page }) => {
    await page.goto("/path-traversal");

    await expect(page.getByRole("button", { name: "Path", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Dependencies", exact: true })).toBeVisible();
  });

  test("should show empty state message", async ({ page }) => {
    await page.goto("/path-traversal");

    await expect(page.getByText('Select two objects and click "Find Paths"')).toBeVisible();
  });

  test("should switch to Dependencies mode", async ({ page }) => {
    await page.goto("/path-traversal");

    await page.getByRole("button", { name: "Dependencies", exact: true }).click();

    await expect(page.getByRole("heading", { name: "Dependencies" })).toBeVisible();
    await expect(
      page.getByText('Select a source object, target kinds, and click "Find Dependencies"')
    ).toBeVisible();
  });

  test("should collapse and expand left panel", async ({ page }) => {
    await page.goto("/path-traversal");

    await expect(page.getByText("Path Traversal")).toBeVisible();

    await test.step("collapse the panel", async () => {
      await page.getByRole("button", { name: "Collapse panel" }).click();
      await expect(page.getByText("Path Traversal")).not.toBeVisible();
    });

    await test.step("expand the panel", async () => {
      await page.getByRole("button", { name: "Expand panel" }).click();
      await expect(page.getByText("Path Traversal")).toBeVisible();
    });
  });

  test("should toggle Advanced Options section", async ({ page }) => {
    await page.goto("/path-traversal");

    const advancedToggle = page.getByText("Advanced Options");

    if (await advancedToggle.isVisible()) {
      await advancedToggle.click();
    }
  });
});
