import { expect, test } from "@playwright/test";
import { format } from "date-fns";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("Getting started with Infrahub - Object and branch creation, update, diff and merge", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  let dateBeforeTest: Date;

  test("1. Create a new organization", async ({ page }) => {
    dateBeforeTest = new Date();

    await page.goto("/");

    await page.getByTestId("sidebar").getByRole("button", { name: "Organization" }).click();
    await page.getByRole("menuitem", { name: "Tenant" }).click();

    await test.step("fill and submit form for new organization", async () => {
      await page.getByTestId("create-object-button").click();

      await page.getByLabel("Name *").fill("my-first-tenant");
      await page.getByLabel("Description").fill("Testing Infrahub");
      await saveScreenshotForDocs(page, "tutorial_1_organization_create");

      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("confirm creation and update UI", async () => {
      await expect(page.locator("#alert-success-Tenant-created")).toContainText("Tenant created");
      const tenantRow = page.locator("tbody >> tr").filter({ hasText: "my-first-tenant" });
      await expect(tenantRow).toContainText("my-first-tenant");
      await expect(tenantRow).toContainText("Testing Infrahub");
    });
  });

  test("2. Create a new branch", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("branch-selector-trigger").click();
    await page.getByTestId("create-branch-button").click();

    await test.step("fill and submit form for new organization", async () => {
      await expect(page.getByText("Create a new branch")).toBeVisible();
      await page.getByLabel("New branch name *").fill("cr1234");
      await saveScreenshotForDocs(page, "tutorial_1_branch_creation");
      await page.getByRole("button", { name: "Create a new branch" }).click();
    });

    // After submit
    await expect(page.getByTestId("branch-selector-trigger")).toContainText("cr1234");
    await expect(page).toHaveURL(/.*?branch=cr1234/);
  });

  test("3. Update an organization", async ({ page }) => {
    await test.step("Go to the newly created organization on branch cr1234", async () => {
      await page.goto("/?branch=cr1234");

      await page.getByTestId("sidebar").getByRole("button", { name: "Organization" }).click();
      await page.getByRole("menuitem", { name: "Tenant" }).click();

      const myFirstOrgLink = page.getByRole("link", { name: "my-first-tenant" });
      await expect(myFirstOrgLink).toBeVisible();
      await saveScreenshotForDocs(page, "tutorial_1_organizations");
      await myFirstOrgLink.click();
    });

    await test.step("Edit the organization description on branch cr1234", async () => {
      const editButton = page.getByTestId("edit-button");
      await expect(editButton).toBeVisible();
      await saveScreenshotForDocs(page, "tutorial_1_organization_details");
      await editButton.click();

      await page.getByLabel("Description").fill("Changes from branch cr1234");
      await saveScreenshotForDocs(page, "tutorial_1_organization_edit");
      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Update confirmation and update UI", async () => {
      await expect(page.getByText("Tenant updated")).toBeVisible();
      await expect(page.getByText("Changes from branch cr1234")).toBeVisible();
    });

    await test.step("See initial value on main branch", async () => {
      await page.getByTestId("branch-selector-trigger").click();
      await page.getByRole("option", { name: "main default" }).click();
      await expect(page.getByText("Testing Infrahub")).toBeVisible();
    });
  });

  test("4. View the Diff and Merge the branch cr1234 into main", async ({ page }) => {
    await test.step("Go to branch cr1234 page", async () => {
      await page.goto("/?branch=cr1234");
      await page.getByTestId("branch-selector-trigger").click();
      await page.getByRole("link", { name: "View all branches" }).click();
      await saveScreenshotForDocs(page, "tutorial_1_branch_list");
      await page.getByTestId("branches-items").getByText("cr1234").click();
      await expect(page.locator("dl")).toContainText("cr1234");
    });

    await test.step("trigger the diff update", async () => {
      await page.getByText("Data").click();
      await expect(page.getByText("We are computing the diff")).toBeVisible();
      await page.getByRole("button", { name: "Refresh" }).click();
      await expect(page.getByText("Diff updated!")).toBeVisible();
    });

    await test.step("View branch diff", async () => {
      await page.getByText("UpdatedTenantmy-first-Tenant").click();
      await expect(page.getByText("Testing Infrahub")).toBeVisible();
      await saveScreenshotForDocs(page, "tutorial_1_branch_diff");
      await expect(page.getByText("Changes from branch cr1234")).toBeVisible();
    });

    await test.step("Merge branch cr1234 into main", async () => {
      await page.getByText("Details", { exact: true }).click();
      const mergeButton = page.getByRole("button", { name: "Merge" });
      await expect(mergeButton).toBeVisible();
      await saveScreenshotForDocs(page, "tutorial_1_branch_details");
      await mergeButton.click();
      await expect(page.locator("#alert-success")).toContainText("Branch merged successfully!");
      await expect(page.locator("pre")).toContainText(
        // eslint-disable-next-line quotes
        '{ "data": { "BranchMerge": { "ok": true, "__typename": "BranchMerge" } } }'
      );
    });

    await test.step("Validate merged changes in main", async () => {
      await page.getByTestId("branch-selector-trigger").click();
      await page.getByRole("option", { name: "main default" }).click();
      await expect(page.getByTestId("branch-selector-trigger")).toContainText("main");

      await page.getByTestId("sidebar").getByRole("button", { name: "Organization" }).click();
      await page.getByRole("menuitem", { name: "Tenant" }).click();

      await expect(page.locator("tbody")).toContainText("Changes from branch cr1234");
    });
  });

  test("5. Browse historical data", async ({ page }) => {
    await page.goto("/objects/OrganizationTenant");

    await test.step("Row my-first-tenant is visible at current time", async () => {
      await expect(page.getByRole("link", { name: "my-first-tenant" })).toBeVisible();
    });

    await test.step("Row my-first-tenant is not visible when date prior to its creation is selected", async () => {
      await page.getByTestId("timeframe-selector").click();
      await saveScreenshotForDocs(page, "tutorial_2_historical");
      await page
        .getByRole("option", { name: format(dateBeforeTest, "h:mm aa"), exact: true })
        .click();
      await expect(page.getByRole("link", { name: "Duff" })).toBeVisible();
      await expect(
        page.getByRole("link", { name: "Changes from branch cr1234" })
      ).not.toBeVisible();
    });

    await test.step("Row my-first-tenant is visible again when we reset date input", async () => {
      await page.getByTestId("reset-timeframe-selector").click();
      await expect(page.getByRole("link", { name: "Changes from branch cr1234" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Testing Infrahub" })).not.toBeVisible();
    });
  });
});
