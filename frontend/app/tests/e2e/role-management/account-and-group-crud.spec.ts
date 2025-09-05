import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, saveScreenshotForDocs } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("Account management - CRUD", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.describe.configure({ mode: "serial" });

  const BRANCH_NAME = generateRandomBranchName();

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("Should create an account ", async ({ page }) => {
    await test.step("access main view", async () => {
      await page.goto(`/role-management?branch=${BRANCH_NAME}`);
    });

    await test.step("create account", async () => {
      await expect(page.getByText("Retrieving accounts...")).not.toBeVisible();
      await page.getByTestId("create-object-button").click();
      await page.getByRole("textbox", { name: "Name *" }).fill("new-user");
      await page.getByRole("textbox", { name: "Password *" }).fill("password123");
      await page.getByRole("textbox", { name: "Name *" }).click();
      await saveScreenshotForDocs(page, "guides/permissions/permissions_account");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Account created!")).toBeVisible();
    });

    await test.step("verify account creation", async () => {
      await expect(page.getByRole("cell", { name: "new-user" })).toBeVisible();
    });
  });

  test("Should create an group", async ({ page }) => {
    await test.step("access main view", async () => {
      await page.goto(`/role-management/groups?branch=${BRANCH_NAME}`);
    });

    await test.step("create group", async () => {
      await expect(page.getByText("Retrieving groups...")).not.toBeVisible();
      await page.getByRole("button", { name: "Create Account group" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("New Group");

      await page.getByRole("combobox", { name: "Type" }).click();
      await page.getByRole("option", { name: "default" }).click();
      await page.getByTestId("side-panel-container").getByText("Roles").click();
      await page.getByTestId("side-panel-container").getByText("Own branches read-write").click();
      await page.getByTestId("side-panel-container").getByText("Members").click();
      await page.getByText("New-User").click();

      await page.getByRole("textbox", { name: "Name *" }).click();
      await saveScreenshotForDocs(page, "guides/permissions/permissions_group");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Group created!")).toBeVisible();
    });

    await test.step("verify group creation", async () => {
      await expect(page.getByRole("cell", { name: "New Group" }).first()).toBeVisible();
    });
  });
  // TODO: Update and Delete Tests
});
