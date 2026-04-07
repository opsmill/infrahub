import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, getDataTableRow } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/role-management/roles - Roles CRUD", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.describe.configure({ mode: "serial" });

  const BRANCH_NAME = generateRandomBranchName("role-crud");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should create, edit, bulk edit, and delete roles", async ({ page }) => {
    await test.step("navigate to roles page", async () => {
      await page.goto(`/role-management/roles?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("link", { name: "Administrator", exact: true })).toBeVisible();
    });

    await test.step("create a new role", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("textbox", { name: "Name *" }).fill("test role");
      await page.getByLabel("Groups").click();
      await page.getByTestId("side-panel-container").getByText("Infrahub Users").click();
      await page.getByLabel("Groups").click();
      await page.getByTestId("side-panel-container").getByLabel("Permissions").click();
      await page
        .getByTestId("side-panel-container")
        .getByRole("option", { name: "global:super_admin:allow_all" })
        .click();
      await page.getByTestId("side-panel-container").getByLabel("Permissions").click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Role created!")).toBeVisible();
    });

    await test.step("verify role columns are displayed", async () => {
      const row = getDataTableRow(page, "test role");
      await expect(row.getByRole("link", { name: "Infrahub Users" })).toBeVisible();
      await expect(row.getByText("global:super_admin:allow_all")).toBeVisible();
    });

    await test.step("open edit form and verify field values", async () => {
      await page.getByTestId("actions-cell-test role").click();
      await page.getByRole("menuitem", { name: "Edit" }).click();
      await expect(page.getByRole("textbox", { name: "Name *" })).toHaveValue("test role");
      await expect(page.getByLabel("Groups").locator("..")).toContainText("Infrahub Users");
      await expect(page.getByLabel("Permissions").locator("..")).toContainText(
        "global:super_admin:allow_all"
      );
    });

    await test.step("update the role name and save", async () => {
      await page.getByRole("textbox", { name: "Name *" }).fill("test role updated");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Role updated!")).toBeVisible();
      await expect(page.getByRole("link", { name: "test role updated" })).toBeVisible();
    });

    await test.step("create a second role", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("textbox", { name: "Name *" }).fill("test role 2");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Role created!")).toBeVisible();
      await expect(page.getByRole("link", { name: "test role 2" })).toBeVisible();
    });

    await test.step("bulk edit both roles", async () => {
      await page
        .getByRole("link", { name: "test role updated" })
        .locator("..")
        .getByTestId("identifier-checkbox-cell")
        .click();
      await page
        .getByRole("link", { name: "test role 2" })
        .locator("..")
        .getByTestId("identifier-checkbox-cell")
        .click();
      await page.getByRole("button", { name: "Edit" }).click();
      await page.getByRole("button", { name: "Add Permissions" }).click();
      await page.getByRole("option", { name: "global:super_admin:allow_all" }).click();
      await page.getByRole("button", { name: "Add Permissions" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await page.getByRole("heading", { name: "2 / 2 objects updated" }).click();
      await page.keyboard.press("Escape");
    });

    await test.step("verify bulk edit applied permissions", async () => {
      const row1 = getDataTableRow(page, "test role updated");
      const row2 = getDataTableRow(page, "test role 2");
      await expect(row1.getByText("global:super_admin:allow_all")).toBeVisible();
      await expect(row2.getByText("global:super_admin:allow_all")).toBeVisible();
    });

    await test.step("delete the first role", async () => {
      await page.getByTestId("actions-cell-test role updated").click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Object test role updated deleted")).toBeVisible();
      await expect(page.getByRole("link", { name: "test role 2" })).toBeVisible();
      await expect(page.getByRole("link", { name: "test role updated" })).not.toBeVisible();
    });

    await test.step("bulk delete the remaining role", async () => {
      await expect(page.getByRole("link", { name: "test role 2" })).toBeVisible();
      await page.getByRole("button", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Objects deleted!")).toBeVisible();
      await expect(page.getByRole("link", { name: "test role 2" })).not.toBeVisible();
    });
  });
});
