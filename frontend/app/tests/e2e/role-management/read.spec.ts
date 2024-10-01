import { test, expect } from "@playwright/test";

test.describe("Role management - READ", () => {
  test("should read correctly the different views", async ({ page }) => {
    await test.step("access main view", async () => {
      await page.goto("/role-management");
    });

    await test.step("check counts", async () => {
      await expect(page.getByRole("link", { name: "Accounts 9" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Groups 1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Roles 1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Global Permissions 1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Object Permissions 0" })).toBeVisible();
    });

    await test.step("check accounts view", async () => {
      await expect(page.getByRole("cell", { name: "Admin" })).toBeVisible();
      await expect(page.getByRole("cell", { name: "Pop-Builder" })).toBeVisible();
    });

    await test.step("check groups view", async () => {
      await page.getByRole("link", { name: "Groups 1" }).click();
      await expect(page.getByRole("cell", { name: "Administrators" })).toBeVisible();
      await expect(page.getByRole("cell", { name: "+ 4" })).toBeVisible();
    });

    await test.step("check roles view", async () => {
      await page.getByRole("link", { name: "Roles 1" }).click();
      await expect(page.getByRole("cell", { name: "Super Administrator" })).toBeVisible();
      await expect(page.getByRole("cell", { name: "1" }).first()).toBeVisible();
    });

    await test.step("check global permissions view", async () => {
      await page.getByRole("link", { name: "Global Permissions" }).click();
      await expect(page.getByRole("cell", { name: "Edit Default Branch" })).toBeVisible();
      await expect(page.getByRole("cell", { name: "1" })).toBeVisible();
      await expect(page.getByText("global:edit_default_branch:")).toBeVisible();
    });
  });
});
