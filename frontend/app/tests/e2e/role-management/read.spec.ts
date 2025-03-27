import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Role management - READ", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should read correctly the different views", async ({ page }) => {
    await test.step("access main view", async () => {
      await page.goto("/role-management");
    });

    await test.step("check counts", async () => {
      await expect(page.getByRole("link", { name: "Accounts 12" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Groups 6" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Roles 7" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Global Permissions 8" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Object Permissions 4" })).toBeVisible();
    });

    await test.step("check accounts view", async () => {
      await expect(page.getByRole("cell", { name: "admin", exact: true })).toBeVisible();
      await expect(page.getByRole("cell", { name: "Pop-Builder" })).toBeVisible();
    });

    await test.step("check groups view", async () => {
      await page.getByRole("link", { name: "Groups 6" }).click();
      await expect(page.getByText("Showing 1 to 6 of 6 results")).toBeVisible();
      await expect(
        page.getByTestId("breadcrumb-navigation").getByRole("link", { name: "Groups" })
      ).toBeVisible();
      await expect(page.getByRole("cell", { name: "Operations Team" })).toBeVisible();
    });

    await test.step("check roles view", async () => {
      await page.getByRole("link", { name: "Roles 7" }).click();
      await expect(page.getByText("General Access")).toBeVisible();
      await expect(page.getByText("Infrahub Users")).toBeVisible();
      await expect(page.getByText("global:edit_default_branch:")).toBeVisible();
      await expect(page.getByRole("cell", { name: "1" }).first()).toBeVisible();
    });

    await test.step("check global permissions view", async () => {
      await page.getByRole("link", { name: "Global Permissions" }).click();
      await expect(page.getByRole("cell", { name: "super_admin", exact: true })).toBeVisible();
      await expect(page.getByText("global:super_admin:")).toBeVisible();
    });
  });
});
