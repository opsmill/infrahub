import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, getDataTableRow } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/role-management - Account CRUD", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.describe.configure({ mode: "serial" });

  const BRANCH_NAME = generateRandomBranchName("account-management");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should create, edit, bulk edit, manage groups, and delete accounts", async ({ page }) => {
    await test.step("navigate to role management page", async () => {
      await page.goto(`/role-management?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("link", { name: "Admin", exact: true })).toBeVisible();
    });

    await test.step("create a new account", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("textbox", { name: "Name *" }).fill("account test");
      await page.getByRole("textbox", { name: "Password *" }).fill("123");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Account created!")).toBeVisible();
      await expect(page.getByRole("link", { name: "Account Test" })).toBeVisible();
    });

    await test.step("edit the account description", async () => {
      await getDataTableRow(page, "Account Test").getByTestId("actions-cell-Account Test").click();
      await page.getByRole("menuitem", { name: "Edit" }).click();
      await page.getByRole("textbox", { name: "Description" }).fill("test edit");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Account updated!")).toBeVisible();
      await expect(getDataTableRow(page, "Account Test").getByText("test edit")).toBeVisible();
    });

    await test.step("create a second account", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("textbox", { name: "Name *" }).fill("Account test 2");
      await page.getByRole("textbox", { name: "Password *" }).fill("123");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(getDataTableRow(page, "Account Test 2")).toBeVisible();
    });

    await test.step("bulk edit both accounts", async () => {
      await getDataTableRow(page, "Account Test").getByTestId("identifier-checkbox-cell").click();
      await getDataTableRow(page, "Account Test 2").getByTestId("identifier-checkbox-cell").click();
      await page.getByRole("button", { name: "Edit" }).click();
      await page.getByRole("textbox", { name: "Description" }).fill("test bulk edit");
      await page.getByRole("button", { name: "Save" }).click();
      await page.getByRole("heading", { name: "2 / 2 objects updated" }).click();
      await page.keyboard.press("Escape");
      await expect(getDataTableRow(page, "Account Test").getByText("test bulk edit")).toBeVisible();
      await expect(
        getDataTableRow(page, "Account Test 2").getByText("test bulk edit")
      ).toBeVisible();
    });

    await test.step("bulk add accounts to a group", async () => {
      await page.getByRole("button", { name: "Add to groups" }).click();
      await page.getByRole("option", { name: "Infrahub Users" }).click();
      await page.getByRole("button", { name: "Validate" }).click();
      await expect(
        page.getByRole("heading", { name: "1 / 1 group updated successfully" })
      ).toBeVisible();
      await page.getByRole("button", { name: "Close" }).click();
      await expect(
        getDataTableRow(page, "Account Test").getByRole("link", { name: "Infrahub Users" })
      ).toBeVisible();
      await expect(
        getDataTableRow(page, "Account Test 2").getByRole("link", { name: "Infrahub Users" })
      ).toBeVisible();
    });

    await test.step("bulk remove accounts from a group", async () => {
      await page.getByRole("button", { name: "Remove from groups" }).click();
      await page.getByRole("option", { name: "Infrahub Users" }).click();
      await page.getByRole("button", { name: "Validate" }).click();
      await expect(
        page.getByRole("heading", { name: "1 / 1 group updated successfully" })
      ).toBeVisible();
      await page.getByRole("button", { name: "Close" }).click();
      await expect(
        getDataTableRow(page, "Account Test").getByRole("link", { name: "Infrahub Users" })
      ).not.toBeVisible();
      await expect(
        getDataTableRow(page, "Account Test 2").getByRole("link", { name: "Infrahub Users" })
      ).not.toBeVisible();
    });

    await test.step("delete the first account", async () => {
      await getDataTableRow(page, "Account Test")
        .getByTestId("actions-cell-Account Test")
        .click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Object Account Test deleted")).toBeVisible();
      await expect(getDataTableRow(page, "Account Test 2")).toBeVisible();
      await expect(getDataTableRow(page, "Account Test")).not.toBeVisible();
    });

    await test.step("bulk delete the remaining account", async () => {
      await getDataTableRow(page, "Account Test 2")
        .getByTestId("identifier-checkbox-cell")
        .click();
      await page.getByRole("button", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Objects deleted!")).toBeVisible();
      await expect(getDataTableRow(page, "Account Test 2")).not.toBeVisible();
    });
  });
});
