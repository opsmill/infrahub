import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
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
      await expect(page.getByRole("link", { name: "Infrahub Users" })).toBeVisible();
    });

    await test.step("create a new group", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("textbox", { name: "Name *" }).fill("test group");
      await page.getByRole("textbox", { name: "Label" }).fill("Test Group Label");
      await page.getByRole("textbox", { name: "Description" }).fill("A test group");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Group created!")).toBeVisible();
      await expect(page.getByRole("link", { name: "test group" })).toBeVisible();
    });

    await test.step("verify group columns are displayed", async () => {
      await expect(page.getByText("Test Group Label")).toBeVisible();
      await expect(page.getByText("A test group")).toBeVisible();
    });

    await test.step("edit the group description", async () => {
      await page.getByTestId("actions-cell-test group").click();
      await page.getByRole("menuitem", { name: "Edit" }).click();
      await page.getByRole("textbox", { name: "Description" }).fill("updated description");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Group updated!")).toBeVisible();
      await expect(page.getByText("updated description")).toBeVisible();
    });

    await test.step("create a second group", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("textbox", { name: "Name *" }).fill("test group 2");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByRole("link", { name: "test group 2" })).toBeVisible();
    });

    await test.step("bulk edit both groups", async () => {
      await page
        .getByRole("link", { name: "test group", exact: true })
        .locator("..")
        .getByTestId("identifier-checkbox-cell")
        .click();
      await page
        .getByRole("link", { name: "test group 2" })
        .locator("..")
        .getByTestId("identifier-checkbox-cell")
        .click();
      await page.getByRole("button", { name: "Edit" }).click();
      await page.getByRole("textbox", { name: "Description" }).fill("bulk edited");
      await page.getByRole("button", { name: "Save" }).click();
      await page.getByRole("heading", { name: "2 / 2 objects updated" }).click();
      await page.keyboard.press("Escape");
      await expect(page.getByText("bulk edited").first()).toBeVisible();
      await expect(page.getByText("bulk edited").nth(1)).toBeVisible();
    });

    await test.step("delete the first group", async () => {
      await page.getByTestId("actions-cell-test group").click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Object test group deleted")).toBeVisible();
      await expect(page.getByRole("link", { name: "test group 2" })).toBeVisible();
      await expect(page.getByRole("link", { name: "test group", exact: true })).not.toBeVisible();
    });

    await test.step("bulk delete the remaining group", async () => {
      await expect(page.getByRole("link", { name: "test group" })).toBeVisible();
      await page.getByRole("button", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Objects deleted!")).toBeVisible();
      await expect(page.getByRole("link", { name: "test group 2" })).not.toBeVisible();
    });
  });
});
