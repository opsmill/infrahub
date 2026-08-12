import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, getDataTableRow } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/role-management/object-permissions - Object Permissions CRUD", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.describe.configure({ mode: "serial" });

  const BRANCH_NAME = generateRandomBranchName("object-permissions");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should create, edit, and delete an object permission", async ({ page }) => {
    await test.step("navigate to object permissions page", async () => {
      await page.goto(`/role-management/object-permissions?branch=${BRANCH_NAME}`);
      await expect(getDataTableRow(page, "object:*:*:any:allow_all")).toBeVisible();
    });

    await test.step("open create form and fill fields", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Namespace").click();
      await page.getByRole("option", { name: "Builtin" }).click();
      await page.getByLabel("Name", { exact: true }).click();
      await page.getByRole("option", { name: "*" }).click();
      await page.getByLabel("Action *").click();
      await page.getByRole("option", { name: "View" }).click();
      await page.getByLabel("Decision *").click();
      await page.getByRole("option", { name: "Deny everywhere" }).click();
      await page.getByLabel("Roles").click();
      await page.getByRole("option", { name: "Administrator", exact: true }).click();
      await page.getByLabel("Roles").click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Object permission created!")).toBeVisible();
    });

    await test.step("verify new permission in table", async () => {
      const row = getDataTableRow(page, "object:Builtin:*:view:deny");
      await expect(row).toBeVisible();
      await expect(row.getByText("view", { exact: true })).toBeVisible();
      await expect(row.getByText("Deny everywhere")).toBeVisible();
      await expect(row.getByText("Administrator")).toBeVisible();
    });

    await test.step("open edit form and verify field values", async () => {
      await page.getByTestId("actions-cell-object:Builtin:*:view:deny").click();
      await page.getByRole("menuitem", { name: "Edit" }).click();
      await expect(page.getByLabel("Namespace")).toContainText("Builtin");
      await expect(page.getByLabel("Name", { exact: true })).toContainText("*");
      await expect(page.getByLabel("Action *")).toContainText("View");
      await expect(page.getByLabel("Decision *")).toContainText("Deny everywhere");
      await page.getByLabel("Decision *").click();
      await page.getByRole("option", { name: "Allow on other branches" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Object permission updated!")).toBeVisible();
    });

    await test.step("verify updated permission in table", async () => {
      const row = getDataTableRow(page, "object:Builtin:*:view:allow_other");
      await expect(row).toBeVisible();
      await expect(row.getByText("view", { exact: true })).toBeVisible();
      await expect(row.getByText("Allow on other branches")).toBeVisible();
    });

    await test.step("delete the permission", async () => {
      await page.getByTestId("actions-cell-object:Builtin:*:view:allow_other").click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(
        page.getByText("Object object:Builtin:*:view:allow_other deleted")
      ).toBeVisible();
      await expect(getDataTableRow(page, "object:Builtin:*:view:allow_other")).not.toBeVisible();
    });
  });
});
