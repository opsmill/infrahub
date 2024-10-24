import { expect, test } from "@playwright/test";

test.describe("Role management - READ", () => {
  test("should read correctly the different views", async ({ page }) => {
    await test.step("access main view", async () => {
      await page.goto("/role-management");
    });

    await test.step("check counts", async () => {
      await expect(page.getByRole("link", { name: "Accounts 9" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Groups 2" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Roles 2" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Global Permissions 8" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Object Permissions 2" })).toBeVisible();
    });

    await test.step("check accounts view", async () => {
      await expect(page.getByRole("cell", { name: "admin", exact: true })).toBeVisible();
      await expect(page.getByRole("cell", { name: "Pop-Builder" })).toBeVisible();
    });

    await test.step("check groups view", async () => {
      await page.getByRole("link", { name: "Groups 2" }).click();
      await expect(page.getByRole("cell", { name: "Administrators" })).toBeVisible();
      await expect(page.getByRole("button", { name: "+4" })).toBeVisible();
    });

    await test.step("check roles view", async () => {
      await page.getByRole("link", { name: "Roles 2" }).click();
      await expect(page.getByText("General Access")).toBeVisible();
      await expect(page.getByText("Infrahub Users")).toBeVisible();
      await expect(page.getByText("global:manage_repositories:")).toBeVisible();
    });

    await test.step("check global permissions view", async () => {
      await page.getByRole("link", { name: "Global Permissions" }).click();
      await expect(page.getByRole("cell", { name: "super_admin", exact: true })).toBeVisible();
      await expect(page.getByText("global:super_admin:allow")).toBeVisible();
    });
  });
});
