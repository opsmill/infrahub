import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";

test.describe("/objects/:objectKind - Bulk edit some rows", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  const BRANCH_NAME = generateRandomBranchName("select-range");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should select range forward (lower to higher index)", async ({ page }) => {
    await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
    await page.getByTestId("identifier-checkbox-cell").nth(1).click();
    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(3)
      .click({ modifiers: ["Shift"] });

    await expect(page.getByTestId("identifier-checkbox-cell").nth(0)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(1)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(2)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(3)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(4)).not.toBeChecked();
  });

  test("should select range backward (higher to lower index)", async ({ page }) => {
    await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
    await page.getByTestId("identifier-checkbox-cell").nth(4).click();
    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(1)
      .click({ modifiers: ["Shift"] });

    await expect(page.getByTestId("identifier-checkbox-cell").nth(0)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(1)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(2)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(3)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(4)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(5)).not.toBeChecked();
  });

  test("should select range starting from first row (index 0)", async ({ page }) => {
    await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
    await page.getByTestId("identifier-checkbox-cell").nth(0).click();
    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(2)
      .click({ modifiers: ["Shift"] });

    await expect(page.getByTestId("identifier-checkbox-cell").nth(0)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(1)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(2)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(3)).not.toBeChecked();
  });

  test("should extend range with additional shift-click", async ({ page }) => {
    await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
    await page.getByTestId("identifier-checkbox-cell").nth(1).click();
    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(3)
      .click({ modifiers: ["Shift"] });

    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(5)
      .click({ modifiers: ["Shift"] });

    await expect(page.getByTestId("identifier-checkbox-cell").nth(0)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(1)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(2)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(3)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(4)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(5)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(6)).not.toBeChecked();
  });

  test("should shrink range with shift-click closer to anchor", async ({ page }) => {
    await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
    await page.getByTestId("identifier-checkbox-cell").nth(1).click();
    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(5)
      .click({ modifiers: ["Shift"] });

    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(3)
      .click({ modifiers: ["Shift"] });

    await expect(page.getByTestId("identifier-checkbox-cell").nth(0)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(1)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(2)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(3)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(4)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(5)).not.toBeChecked();
  });

  test("should deselect range forward when shift-clicking a selected row", async ({ page }) => {
    await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
    await page.getByTestId("identifier-checkbox-cell").nth(1).click();
    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(4)
      .click({ modifiers: ["Shift"] });

    await page.getByTestId("identifier-checkbox-cell").nth(1).click();
    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(3)
      .click({ modifiers: ["Shift"] });

    await expect(page.getByTestId("identifier-checkbox-cell").nth(0)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(1)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(2)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(3)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(4)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(5)).not.toBeChecked();
  });

  test("should deselect range backward when shift-clicking a selected row", async ({ page }) => {
    await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
    await page.getByTestId("identifier-checkbox-cell").nth(1).click();
    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(4)
      .click({ modifiers: ["Shift"] });

    await page.getByTestId("identifier-checkbox-cell").nth(3).click();
    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(1)
      .click({ modifiers: ["Shift"] });

    await expect(page.getByTestId("identifier-checkbox-cell").nth(0)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(1)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(2)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(3)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(4)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(5)).not.toBeChecked();
  });

  test("should reset anchor after selecting all rows", async ({ page }) => {
    await page.goto(`/objects/BuiltinTag?branch=${BRANCH_NAME}`);
    await expect(page.getByTestId("identifier-checkbox-cell")).toHaveCount(3);
    await page.getByTestId("select-all-rows").click();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(0)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(1)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(2)).toBeChecked();

    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(1)
      .click({ modifiers: ["Shift"] });

    await expect(page.getByTestId("identifier-checkbox-cell").nth(0)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(1)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(2)).toBeChecked();
  });

  test("should use last click as shift-click anchor", async ({ page }) => {
    await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
    await page.getByTestId("identifier-checkbox-cell").nth(6).click();
    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(2)
      .click({ modifiers: ["Shift"] });

    await page.getByTestId("identifier-checkbox-cell").nth(4).click();
    await page
      .getByTestId("identifier-checkbox-cell")
      .nth(3)
      .click({ modifiers: ["Shift"] });

    await expect(page.getByTestId("identifier-checkbox-cell").nth(0)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(1)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(2)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(3)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(4)).not.toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(5)).toBeChecked();
    await expect(page.getByTestId("identifier-checkbox-cell").nth(6)).toBeChecked();
  });
});
