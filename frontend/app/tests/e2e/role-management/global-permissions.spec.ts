import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, getDataTableRow } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/role-management/global-permissions - Global Permissions CRUD", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.describe.configure({ mode: "serial" });

  const BRANCH_NAME = generateRandomBranchName("global-permissions");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should create a new global permission", async ({ page }) => {
    await test.step("navigate to global permissions page", async () => {
      await page.goto(`/role-management/global-permissions?branch=${BRANCH_NAME}`);
      await expect(getDataTableRow(page, "global:super_admin:allow_all")).toBeVisible();
    });

    await test.step("open create form and fill fields", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Action *").click();
      await page.getByRole("option", { name: "Update Object Hfid Display" }).click();
      await page.getByLabel("Decision").click();
      await page.getByRole("option", { name: "Deny" }).click();
      await page.getByLabel("Roles").click();
      await page.getByRole("option", { name: "Anonymous User" }).click();
      await page.getByLabel("Roles").click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Global permission created!")).toBeVisible();
    });

    await test.step("verify new permission in table", async () => {
      const row = getDataTableRow(page, "global:update_object_hfid_display_label:deny");
      await expect(row.getByText("Update Object Hfid Display")).toBeVisible();
      await expect(row.getByText("Deny everywhere")).toBeVisible();
      await expect(row.getByText("Anonymous User")).toBeVisible();
    });

    await test.step("open edit form and verify field values", async () => {
      await page.getByTestId("actions-cell-global:update_object_hfid_display_label:deny").click();
      await page.getByRole("menuitem", { name: "Edit" }).click();
      await expect(page.getByLabel("Action *")).toContainText("Update Object Hfid Display");
      await expect(page.getByLabel("Decision")).toContainText("Deny everywhere");
      await expect(page.getByLabel("Roles")).toContainText("Anonymous User");
    });

    await test.step("change decision to Allow and save", async () => {
      await page.getByLabel("Decision").click();
      await page.getByRole("option", { name: "Allow in all branches" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Global permission updated!")).toBeVisible();
    });

    await test.step("verify updated permission in table", async () => {
      const row = getDataTableRow(page, "global:update_object_hfid_display_label:allow_all");
      await expect(row.getByText("Update Object Hfid Display")).toBeVisible();
      await expect(row.getByText("Allow in all branches")).toBeVisible();
      await expect(row.getByText("Anonymous User")).toBeVisible();
    });

    await test.step("delete the permission", async () => {
      await page
        .getByTestId("actions-cell-global:update_object_hfid_display_label:allow_all")
        .click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(
        page.getByText("Object global:update_object_hfid_display_label:allow_all deleted")
      ).toBeVisible();
      await expect(
        getDataTableRow(page, "global:update_object_hfid_display_label:allow_all")
      ).not.toBeVisible();
    });
  });
});
