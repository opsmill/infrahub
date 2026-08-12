import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, getDataTableRow } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/role-management/groups - Group CRUD", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.describe.configure({ mode: "serial" });

  const BRANCH_NAME = generateRandomBranchName("group-management");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should create, edit, bulk edit, and delete groups", async ({ page }) => {
    await test.step("navigate to groups page", async () => {
      await page.goto(`/role-management/groups?branch=${BRANCH_NAME}`);
      await expect(getDataTableRow(page, "Infrahub Users")).toBeVisible();
    });

    await test.step("create a new group", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("textbox", { name: "Name *" }).fill("test group");
      await page.getByRole("textbox", { name: "Label" }).fill("Test Group Label");
      await page.getByRole("textbox", { name: "Description" }).fill("A test group");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Group created!")).toBeVisible();
    });

    await test.step("verify group columns are displayed", async () => {
      const row = getDataTableRow(page, "test group");
      await expect(row).toBeVisible();
      await expect(row.getByText("Test Group Label")).toBeVisible();
      await expect(row.getByText("A test group")).toBeVisible();
    });

    await test.step("open edit form and verify field values", async () => {
      await getDataTableRow(page, "test group").getByTestId("actions-cell-test group").click();
      await page.getByRole("menuitem", { name: "Edit" }).click();
      await expect(page.getByRole("textbox", { name: "Name *" })).toHaveValue("test group");
      await expect(page.getByRole("textbox", { name: "Label" })).toHaveValue("Test Group Label");
      await expect(page.getByRole("textbox", { name: "Description" })).toHaveValue("A test group");
    });

    await test.step("update the group description and save", async () => {
      await page.getByRole("textbox", { name: "Description" }).fill("updated description");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Group updated!")).toBeVisible();
      await expect(
        getDataTableRow(page, "test group").getByText("updated description")
      ).toBeVisible();
    });

    await test.step("create a second group", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("textbox", { name: "Name *" }).fill("test group 2");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Group created!")).toBeVisible();
      await expect(getDataTableRow(page, "test group 2")).toBeVisible();
    });

    await test.step("bulk edit both groups", async () => {
      await getDataTableRow(page, "test group").locator("label").click();
      await getDataTableRow(page, "test group 2").locator("label").click();
      await page.getByRole("button", { name: "Edit" }).click();
      await page.getByRole("textbox", { name: "Description" }).fill("bulk edited");
      await page.getByRole("button", { name: "Save" }).click();
      await page.getByRole("heading", { name: "2 / 2 objects updated" }).click();
      await page.keyboard.press("Escape");
      await expect(getDataTableRow(page, "test group").getByText("bulk edited")).toBeVisible();
      await expect(getDataTableRow(page, "test group 2").getByText("bulk edited")).toBeVisible();
    });

    await test.step("delete the first group", async () => {
      await getDataTableRow(page, "test group").getByTestId("actions-cell-test group").click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Object test group deleted")).toBeVisible();
      await expect(getDataTableRow(page, "test group 2")).toBeVisible();
      await expect(getDataTableRow(page, "test group")).not.toBeVisible();
    });

    await test.step("bulk delete the remaining group", async () => {
      await page.getByRole("button", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Objects deleted!")).toBeVisible();
      await expect(getDataTableRow(page, "test group 2")).not.toBeVisible();
    });
  });
});
