import { expect, test } from "@playwright/test";
import { format, subMinutes } from "date-fns";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("Getting started with Infrahub - Object and branch creation, update, diff and merge", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("1. Create a new organization", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("sidebar-menu").getByRole("link", { name: "Organization" }).click();

    await test.step("fill and submit form for new organization", async () => {
      await page.getByTestId("create-object-button").click();

      await page.getByLabel("Name *").fill("my-first-org");
      await page.getByLabel("Description").fill("Testing Infrahub");
      await saveScreenshotForDocs(page, "tutorial_1_organization_create");

      await page.getByRole("button", { name: "Create" }).click();
    });

    await test.step("confirm creation and update UI", async () => {
      await expect(page.locator("#alert-success")).toContainText("Organization created");
      await expect(page.locator("tbody")).toContainText("my-first-org");
      await expect(page.locator("tbody")).toContainText("My-First-Org");
      await expect(page.locator("tbody")).toContainText("Testing Infrahub");
    });
  });

  test("2. Create a new branch", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("create-branch-button").click();

    await test.step("fill and submit form for new organization", async () => {
      await expect(page.getByText("Create a new branch")).toBeVisible();
      await page.locator("[id='New branch name']").fill("cr1234");
      await saveScreenshotForDocs(page, "tutorial_1_branch_creation");
      await page.getByRole("button", { name: "Create" }).click();
    });

    // After submit
    await expect(page.getByTestId("branch-select-menu")).toContainText("cr1234");
    await expect(page).toHaveURL(/.*?branch=cr1234/);
  });

  test("3. Update an organization", async ({ page }) => {
    await test.step("Go to the newly created organization on branch cr1234", async () => {
      await page.goto("/?branch=cr1234");
      await page.getByRole("link", { name: "Organization" }).click();
      const myFirstOrgLink = page.getByRole("cell", { name: "my-first-org", exact: true });
      await expect(myFirstOrgLink).toBeVisible();
      await saveScreenshotForDocs(page, "tutorial_1_organizations");
      await myFirstOrgLink.click();
    });

    await test.step("Edit the organization description on branch cr1234", async () => {
      const editButton = page.getByRole("button", { name: "Edit" });
      await expect(editButton).toBeVisible();
      await saveScreenshotForDocs(page, "tutorial_1_organization_details");
      await editButton.click();

      await page.getByLabel("Description").fill("Changes from branch cr1234");
      await saveScreenshotForDocs(page, "tutorial_1_organization_edit");
      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Update confirmation and update UI", async () => {
      await expect(page.locator("#alert-success-updated")).toContainText("Organization updated");
      await expect(page.getByText("Changes from branch cr1234")).toBeVisible();
    });

    await test.step("See initial value on main branch", async () => {
      await page.getByTestId("branch-list-display-button").click();
      await page.getByText("main", { exact: true }).click();
      await expect(page.getByText("Testing Infrahub")).toBeVisible();
    });
  });

  test("4. View the Diff and Merge the branch cr1234 into main", async ({ page }) => {
    await test.step("Go to branch cr1234 page", async () => {
      await page.goto("/?branch=cr1234");
      await page.getByTestId("sidebar-menu").getByRole("link", { name: "Branches" }).click();
      await saveScreenshotForDocs(page, "tutorial_1_branch_list");
      await page.getByTestId("branches-items").getByText("cr1234").click();
      await expect(page.locator("dl")).toContainText("cr1234");
    });

    await test.step("View branch diff", async () => {
      await page.getByRole("button", { name: "Diff" }).click();
      await page.getByText("My-First-Org").click();
      await expect(page.getByText("Testing Infrahub")).toBeVisible();
      await saveScreenshotForDocs(page, "tutorial_1_branch_diff");
      await expect(page.getByText("Changes from branch cr1234")).toBeVisible();
    });

    await test.step("Merge branch cr1234 into main", async () => {
      await page.getByRole("button", { name: "Details" }).click();
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
      await page.getByTestId("branch-list-display-button").click();
      await page.getByTestId("branch-list-dropdown").getByText("main", { exact: true }).click();
      await page.getByTestId("sidebar-menu").getByRole("link", { name: "Organization" }).click();
      await expect(page.locator("tbody")).toContainText("Changes from branch cr1234");
    });
  });

  test("5. Browse historical data", async ({ page }) => {
    await page.goto("/objects/CoreOrganization");

    await test.step("Row my-first-org is visible at current time", async () => {
      await expect(page.locator("tbody")).toContainText("my-first-org");
    });

    await test.step("Row my-first-org is not visible when date prior to its creation is selected", async () => {
      const dateAt5MinAgo = format(subMinutes(new Date(), 50), "iiii, MMMM do,");
      await page.getByTestId("date-picker").locator("input").click();
      await saveScreenshotForDocs(
        page,
        "tutorial/tutorial-2-historical.cy.ts/tutorial_2_historical"
      );
      await page.getByLabel(`Choose ${dateAt5MinAgo}`).click();
      await expect(page.locator("tbody")).not.toContainText("my-first-org");
    });

    await test.step("Row my-first-org is visible again when we reset date input", async () => {
      await page.getByRole("button", { name: "Reset" }).click();
      await expect(page.locator("tbody")).toContainText("my-first-org");
    });
  });
});
