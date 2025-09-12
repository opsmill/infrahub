import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, saveScreenshotForDocs } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("Role management - Roles CRUD", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.describe.configure({ mode: "serial" });

  const BRANCH_NAME = generateRandomBranchName("role-crud");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("Should create a role ", async ({ page }) => {
    await test.step("access main view", async () => {
      await page.goto(`/role-management/roles?branch=${BRANCH_NAME}`);
    });

    await test.step("create role", async () => {
      await expect(page.getByText("Retrieving roles...")).not.toBeVisible();
      await page.getByRole("button", { name: "Create Account role" }).click();
      await page.getByLabel("Name *").click();
      await page.getByLabel("Name *").fill("test role");
      await page.getByLabel("Groups").click();
      await page.getByTestId("side-panel-container").getByText("Infrahub Users").click();
      await page.getByLabel("Groups").click();
      await page.getByTestId("side-panel-container").getByLabel("Permissions").click();
      await page
        .getByTestId("side-panel-container")
        .getByText("global:super_admin:allow_all")
        .first()
        .click();
      await page
        .getByTestId("side-panel-container")
        .getByText("global:manage_repositories:")
        .click();
      await page.getByTestId("side-panel-container").getByLabel("Permissions").click();
      await saveScreenshotForDocs(page, "guides/permissions/permissions_role");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Role created!")).toBeVisible();
    });

    await test.step("verify role creation", async () => {
      await expect(page.getByRole("cell", { name: "test role" })).toBeVisible();
      await expect(
        page
          .getByRole("cell", {
            name: "global:super_admin:allow_all global:manage_repositories:allow_all",
          })
          .locator("div")
          .first()
      ).toBeVisible();
    });
  });

  test("Should update a role ", async ({ page }) => {
    await test.step("access main view", async () => {
      await page.goto(`/role-management/roles?branch=${BRANCH_NAME}`);
    });

    await test.step("update role", async () => {
      await page
        .getByRole("row", { name: "test role Infrahub Users" })
        .getByTestId("actions-row-button")
        .click();
      await page.getByTestId("update-row-button").click();
      await page.getByLabel("Name *").click();
      await page.getByLabel("Name *").fill("test role 2");
      await page.getByTestId("remove-option").first().click();
      await page.getByLabel("Groups").click();
      await page.getByTestId("side-panel-container").getByText("Super Administrators").click();
      await page.getByLabel("Groups").click();
      await page.getByTestId("side-panel-container").getByLabel("Permissions").click();
      await page
        .getByTestId("side-panel-container")
        .getByText("global:manage_schema:allow_all")
        .click();
      await page.getByTestId("side-panel-container").getByLabel("Permissions").click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Role updated!")).toBeVisible();
    });

    await test.step("verify role update", async () => {
      await expect(page.getByText("test role 2")).toBeVisible();
      await expect(page.getByText("Super Administrators").nth(1)).toBeVisible();
    });
  });

  test("Should delete a role ", async ({ page }) => {
    await test.step("access main view", async () => {
      await page.goto(`/role-management/roles?branch=${BRANCH_NAME}`);
    });

    await test.step("delete role", async () => {
      await page
        .getByRole("row", { name: "test role 2" })
        .getByTestId("actions-row-button")
        .click();
      await page.getByTestId("delete-row-button").click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Are you sure you want to remove")).not.toBeVisible();
      await expect(page.getByText("Object test role 2 deleted")).toBeVisible();
    });

    await test.step("verify role delete", async () => {
      await expect(page.getByTestId("objects-search-input-loader")).not.toBeVisible();
      await expect(page.getByText("test role 2")).not.toBeVisible();
    });
  });
});
