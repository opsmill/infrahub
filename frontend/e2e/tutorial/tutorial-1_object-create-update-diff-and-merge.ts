import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../tests/utils";
import { format, subMinutes } from "date-fns";

test.describe("Getting started with Infrahub - Object and branch creation, update, diff and merge", () => {
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

  test("4. View the Diff and Merge the branch cr1234 into main", async ({ page }) => {
    await page.goto("/?branch=cr1234");

    await page.getByTestId("sidebar-menu").getByRole("link", { name: "Branches" }).click();
    await page.getByTestId("branches-items").getByText("cr1234").click();
    await expect(page.locator("dl")).toContainText("cr1234");

    // View diff
    await page.getByRole("button", { name: "Diff" }).click();
    await page.getByText("My-First-Org").click();
    await expect(page.getByText("Testing Infrahub")).toBeVisible();
    await expect(page.getByText("Changes from branch cr1234")).toBeVisible();

    // Merge cr1234 into main branch
    await page.getByRole("button", { name: "Details" }).click();
    await page.getByRole("button", { name: "Merge" }).click();
    await expect(page.locator("#alert-success")).toContainText("Branch merged successfully!");
    await expect(page.locator("pre")).toContainText(
      // eslint-disable-next-line quotes
      '{ "data": { "BranchMerge": { "ok": true, "__typename": "BranchMerge" } } }'
    );

    // Validate that merge is correct
    await page.getByTestId("branch-list-display-button").click();
    await page.getByTestId("branch-list-dropdown").getByText("main", { exact: true }).click();
    await page.getByTestId("sidebar-menu").getByRole("link", { name: "Organization" }).click();
    await expect(page.locator("tbody")).toContainText("Changes from branch cr1234");
  });

  test("5. Browse historical data", async ({ page }) => {
    await page.goto("/objects/CoreOrganization");

    await test.step("Row my-first-org is visible at current time", async () => {
      await expect(page.locator("tbody")).toContainText("my-first-org");
    });

    await test.step("Row my-first-org is not visible when date prior to its creation is selected", async () => {
      const dateAt5MinAgo = format(subMinutes(new Date(), 5), "dd/MM/yyyy HH:mm");
      await page.getByTestId("date-picker").locator("input").fill(dateAt5MinAgo);
      await expect(page.locator("tbody")).not.toContainText("my-first-org");
    });

    await test.step("Row my-first-org is visible again when we reset date input", async () => {
      await page.getByRole("button", { name: "Reset" }).click();
      await expect(page.locator("tbody")).toContainText("my-first-org");
    });
  });
});
