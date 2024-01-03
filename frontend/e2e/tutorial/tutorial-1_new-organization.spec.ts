import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../tests/utils";

test.describe("Getting started with Infrahub", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("1. Create a new organization", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("sidebar-menu").getByRole("link", { name: "Organization" }).click();
    await page.getByTestId("create-object-button").click();

    // Form
    await page.getByLabel("Name *").fill("my-first-org");
    await page.getByLabel("Description").fill("Testing Infrahub");
    await page.getByRole("button", { name: "Create" }).click();

    // Then
    await expect(page.locator("#alert-success")).toContainText("Organization created");
    await expect(page.locator("tbody")).toContainText("my-first-org");
    await expect(page.locator("tbody")).toContainText("My-First-Org");
    await expect(page.locator("tbody")).toContainText("Testing Infrahub");
  });

  test("2. Create a new branch", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("create-branch-button").click();

    // Form
    await expect(page.getByText("Create a new branch")).toBeVisible();
    await page.locator("#new-branch-name").fill("cr1234");
    await page.getByRole("button", { name: "Create" }).click();

    // After submit
    await expect(page.getByTestId("branch-select-menu")).toContainText("cr1234");
    await expect(page).toHaveURL(/.*?branch=cr1234/);
  });

  test("3. Update an organization", async ({ page }) => {
    await page.goto("/?branch=cr1234");
    await page.getByRole("link", { name: "Organization" }).click();
    await page.getByRole("cell", { name: "my-first-org", exact: true }).click();
    await page.getByRole("button", { name: "Edit" }).click();

    // Edit form
    await page.getByLabel("Description").fill("Changes from branch cr1234");
    await page.getByRole("button", { name: "Save" }).click();

    // After submit
    await expect(page.locator("#alert-success")).toContainText("Organization updated");
    await expect(page.getByText("Changes from branch cr1234")).toBeVisible();

    // See initial value on main branch
    await page.getByTestId("branch-list-display-button").click();
    await page.getByText("main", { exact: true }).click();
    await expect(page.getByText("Testing Infrahub")).toBeVisible();
  });
});
