import { test, expect } from "@playwright/test";

test.describe("Role management - READ", () => {
  test("should read correctly the different views", async ({ page }) => {
    await test.step("access main view", async () => {
      await page.goto("http://localhost:8080/role-management");
    });

    await test.step("check counts", async () => {
      await expect(page.getByRole("link", { name: "Accounts 9" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Groups 1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Roles 1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Global Permissions 1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Object Permissions 1" })).toBeVisible();
    });

    await test.step("check accounts view", async () => {
      await expect(page.getByRole("cell", { name: "Admin" })).toBeVisible();
      await expect(page.getByRole("cell", { name: "Pop-Builder" })).toBeVisible();
    });

    await test.step("check groups view", async () => {
      await page.getByRole("link", { name: "Groups 1" }).click();
      await expect(page.getByRole("cell", { name: "Administrators" })).toBeVisible();
      await expect(page.getByRole("cell", { name: "A P JB CS CO + 4" })).toBeVisible();
    });

    await test.step("check roles view", async () => {
      await page.getByRole("link", { name: "Roles 1" }).click();
      await expect(page.getByRole("cell", { name: "Administrator" })).toBeVisible();
      await expect(page.getByRole("cell", { name: "1" })).toBeVisible();
      await expect(page.getByRole("cell", { name: "2" })).toBeVisible();
    });

    await test.step("check global permissions view", async () => {
      await page.getByRole("link", { name: "Global Permissions" }).click();
      await expect(page.getByRole("cell", { name: "Edit Default Branch" })).toBeVisible();
      await expect(page.getByRole("cell", { name: "1" })).toBeVisible();
      await expect(page.getByText("global:edit_default_branch:")).toBeVisible();
    });

    await test.step("check object permissions view", async () => {
      await page.getByRole("link", { name: "Object Permissions" }).click();
      await expect(page.getByRole("cell", { name: "* * * any allow" })).toBeVisible();
      await expect(page.getByRole("cell", { name: "*" }).nth(1)).toBeVisible();
      await expect(page.getByRole("cell", { name: "*" }).nth(2)).toBeVisible();
      await expect(page.getByRole("cell", { name: "any", exact: true })).toBeVisible();
      await expect(page.getByRole("cell", { name: "allow", exact: true })).toBeVisible();
      await expect(page.getByRole("cell", { name: "1" })).toBeVisible();
      await expect(page.getByText("object:*:*:*:any:allow")).toBeVisible();
    });
  });
});
