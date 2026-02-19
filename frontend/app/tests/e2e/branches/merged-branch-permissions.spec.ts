import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI, mergeBranchAPI } from "../utils/graphql";

test.describe("Merged branch - disabled actions", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("merged-branch");
  const TOOLTIP_MESSAGE = "Cannot edit objects on a merged branch";

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
    await mergeBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should show merged status badge on branch details page", async ({ page }) => {
    await page.goto(`/branches/${BRANCH_NAME}`);

    await expect(page.getByRole("heading", { name: BRANCH_NAME })).toBeVisible();
    await expect(page.getByText("Merged", { exact: true })).toBeVisible();
  });

  test("should disable create and row actions on the object list view", async ({ page }) => {
    await page.goto(`/objects/BuiltinTag?branch=${BRANCH_NAME}`);

    await test.step("create button is disabled with tooltip", async () => {
      await expect(page.getByTestId("create-object-button")).toBeDisabled();
      await page.getByTestId("create-object-button").hover({ force: true });
      await expect(page.getByText(TOOLTIP_MESSAGE)).toBeVisible();
    });

    await test.step("row action menu items are disabled", async () => {
      await page.getByTestId("actions-cell-blue").click();
      await expect(page.getByRole("menuitem", { name: "Edit" })).toBeDisabled();
      await expect(page.getByRole("menuitem", { name: "Delete" })).toBeDisabled();
    });
  });

  test("should disable edit button on the object details view", async ({ page }) => {
    await page.goto(`/objects/BuiltinTag?branch=${BRANCH_NAME}`);
    await page.getByRole("link", { name: "blue" }).click();

    await test.step("edit button is disabled with tooltip", async () => {
      await expect(page.getByTestId("edit-button")).toBeDisabled();
      await page.getByTestId("edit-button").hover({ force: true });
      await expect(page.getByText(TOOLTIP_MESSAGE)).toBeVisible();
    });

    await test.step("menu actions are disabled", async () => {
      await page.getByTestId("object-details-menu").click();
      await expect(page.getByRole("menuitem", { name: "Groups" })).toHaveAttribute(
        "aria-disabled",
        "true"
      );
      await expect(page.getByRole("menuitem", { name: "Delete" })).toHaveAttribute(
        "aria-disabled",
        "true"
      );
    });
  });

  test("should disable add relationship button on the relationship view", async ({ page }) => {
    await page.goto(`/objects/InfraPlatform?branch=${BRANCH_NAME}`);
    await page.getByRole("link", { name: "Cisco IOS", exact: true }).click();
    await page.getByRole("link", { name: "Devices 10" }).click();

    await test.step("add relationship button is disabled with tooltip", async () => {
      await expect(page.getByTestId("open-relationship-form-button")).toBeDisabled();
      await page.getByTestId("open-relationship-form-button").hover({ force: true });
      await expect(page.getByText(TOOLTIP_MESSAGE)).toBeVisible();
    });
  });
});
