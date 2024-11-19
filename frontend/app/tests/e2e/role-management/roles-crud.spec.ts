import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Role management - Roles CRUD", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.describe.configure({ mode: "serial" });

  test("should create a role ", async ({ page }) => {
    await test.step("access main view", async () => {
      await page.goto("/role-management/roles");
    });

    await test.step("create role", async () => {
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
        .click();
      await page
        .getByTestId("side-panel-container")
        .getByText("global:manage_repositories:")
        .click();
      await page.getByTestId("side-panel-container").getByLabel("Permissions").click();
      await page.getByRole("button", { name: "Create" }).click();
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

  test("should update a role ", async ({ page }) => {
    await test.step("access main view", async () => {
      await page.goto("/role-management/roles");
    });

    await test.step("update role", async () => {
      await page
        .getByRole("row", { name: "test role Infrahub Users" })
        .getByTestId("actions-row-button")
        .click();
      await page.getByTestId("update-row-button").click();
      await page.getByLabel("Name *").click();
      await page.getByLabel("Name *").fill("test role 2");
      await page.getByLabel("Groups").click();
      await page.getByLabel("", { exact: true }).getByText("Infrahub Users").click();
      await page.getByTestId("side-panel-container").getByText("Super Administrators").click();
      await page.getByLabel("Groups").click();
      await page.getByTestId("side-panel-container").getByLabel("Permissions").click();
      await page
        .getByTestId("side-panel-container")
        .getByText("global:manage_schema:allow_all")
        .click();
      await page.getByLabel("", { exact: true }).getByText("global:super_admin:allow_all").click();
      await page.getByTestId("side-panel-container").getByLabel("Permissions").click();
      await page.getByRole("button", { name: "Update" }).click();
      await expect(page.getByText("Role updated!")).toBeVisible();
    });

    await test.step("verify role update", async () => {
      await expect(page.getByText("test role 2")).toBeVisible();
      await expect(page.getByText("Super Administrators").nth(1)).toBeVisible();
      await expect(
        page.getByRole("cell", {
          name: "global:manage_repositories:allow_all global:manage_schema:allow_all",
          exact: true,
        })
      ).toBeVisible();
    });
  });

  test("should delete a role ", async ({ page }) => {
    await test.step("access main view", async () => {
      await page.goto("/role-management/roles");
    });

    await test.step("delete role", async () => {
      await page
        .getByRole("row", { name: "test role 2" })
        .getByTestId("actions-row-button")
        .click();
      await page.getByTestId("delete-row-button").click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Object test role 2 deleted")).toBeVisible();
    });

    await test.step("verify role delete", async () => {
      await expect(page.getByText("test role 2")).not.toBeVisible();
    });
  });
});
