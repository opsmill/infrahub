import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, saveScreenshotForDocs } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/proposed-changes", () => {
  test.describe.configure({ mode: "serial" });

  test.describe("when not logged in", () => {
    test("should not be able to create a proposed changes", async ({ page }) => {
      await page.goto("/proposed-changes");

      await expect(page.getByRole("heading", { name: "Proposed Change" })).toBeVisible();
      await expect(page.getByTestId("add-proposed-changes-button")).toBeDisabled();
    });
  });

  test.describe("when logged in as Admin", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("allow to create a proposed change", async ({ page }) => {
      await page.goto("/proposed-changes");

      await expect(page.getByRole("heading", { name: "Proposed Change" })).toBeVisible();
      await expect(page.getByTestId("add-proposed-changes-button")).toBeEnabled();
      await page.getByTestId("add-proposed-changes-button").click();
      await expect(page.getByRole("heading", { name: "Create a proposed change" })).toBeVisible();
    });

    test("display validation errors when form is submitted with wrong value", async ({ page }) => {
      await page.goto("/proposed-changes/new");

      await expect(page.getByRole("heading", { name: "Create a proposed change" })).toBeVisible();
      await page.getByRole("button", { name: "Open" }).click();
      await expect(page.getByLabel("Name *").locator("..")).toContainText("Required");
      await expect(page.getByText("Source Branch *").locator("..")).toContainText("Required");
    });

    test.describe("Create, edit and merge proposed change", async () => {
      test.describe.configure({ mode: "serial" });

      const pcName = generateRandomBranchName("pc-e2e");
      const pcNameEdit = generateRandomBranchName("pc-e2e-edit");
      const pcBranchName = generateRandomBranchName("main-copy-for-pc-e2e");

      test.beforeAll(async ({ request }) => {
        await createBranchAPI(request, pcBranchName);
      });

      test.afterAll(async ({ request }) => {
        await deleteBranchAPI(request, pcBranchName);
      });

      test("create new proposed change", async ({ page }) => {
        await page.goto("/proposed-changes/new");
        await expect(page.getByText("Create a proposed Change")).toBeVisible();

        await page.getByLabel("Source Branch *").click();
        await page.getByRole("option", { name: pcBranchName }).click();
        await page.getByLabel("Name *").fill(pcName);
        await page.getByTestId("codemirror-editor").getByRole("textbox").fill("My description");
        await page.getByLabel("Reviewers").click();
        await page.getByRole("option", { name: "Olivia Carter" }).click();
        await page.getByRole("option", { name: "CRM Synchronization" }).click();
        await page.getByLabel("Reviewers").click(); // to close the combobox
        await saveScreenshotForDocs(page, "topics/proposed_change/pc_create_form");

        await page.getByRole("button", { name: "Open" }).click();
        await expect(page.getByText("Proposed change created")).toBeVisible();
      });

      test("display and edit proposed change", async ({ page }) => {
        await page.goto("/proposed-changes");

        await test.step("display created proposed change details", async () => {
          await page.getByText(pcName, { exact: true }).click();
          await expect(page.getByText("Source branch" + pcBranchName)).toBeVisible();
          await expect(page.getByRole("row", { name: "State open" })).toBeVisible();
          await expect(page.getByRole("cell", { name: "Created by" })).toBeVisible();
          await expect(page.getByRole("cell", { name: "Created at" })).toBeVisible();
          await expect(page.getByRole("cell", { name: "Updated by" })).toBeVisible();
          await expect(page.getByRole("cell", { name: "Updated at" })).toBeVisible();
          // Validate the buttons are showing as intended
          await expect(page.getByRole("button", { name: "Approve" })).not.toBeDisabled();
          await saveScreenshotForDocs(page, "topics/proposed_change/pc_tab_overview");
          await page.getByTestId("proposed-change-action-button-select").nth(1).click();
          await expect(page.getByRole("option", { name: "Merge" })).not.toBeDisabled();
          await expect(page.getByRole("option", { name: "Close" })).not.toBeDisabled();
          await expect(page.getByRole("option", { name: "Move to draft" })).not.toBeDisabled();
        });

        await test.step("edit proposed change reviewers", async () => {
          await page.getByTestId("edit-button").click();
          await page.getByLabel("Name").fill(pcNameEdit);
          await page
            .getByTestId("side-panel-container")
            .getByTestId("codemirror-editor")
            .getByRole("textbox")
            .fill("My description edit");
          await page
            .locator("span")
            .filter({ hasText: "CRM Synchronization" })
            .getByLabel("Remove")
            .click();
          await page
            .locator("span")
            .filter({ hasText: "Olivia Carter" })
            .getByLabel("Remove")
            .click();
          await page.getByLabel("Reviewers").click(); // to close the combobox
          await page.getByRole("button", { name: "Save" }).click();
          await expect(page.getByText("ProposedChange updated")).toBeVisible();

          await expect(page.getByRole("heading", { name: pcNameEdit, exact: true })).toBeVisible();
          await expect(page.getByTestId("pc-description")).toContainText("My description edit");
          await expect(page.getByText("OC", { exact: true })).not.toBeVisible();
          await expect(page.getByText("CS", { exact: true })).not.toBeVisible();
        });
      });

      test.fixme("add a comment on overview tab", async ({ page }) => {
        await page.goto("/proposed-changes");
        await page.getByText(pcNameEdit, { exact: true }).first().click();

        await page
          .getByTestId("codemirror-editor")
          .getByRole("textbox")
          .fill("comment on overview tab");
        await page.getByRole("button", { name: "Comment", exact: true }).click();
        await expect(
          page.getByTestId("comment").getByText("comment on overview tab")
        ).toBeVisible();
        await expect(page.getByTestId("codemirror-editor").getByRole("textbox")).toContainText(
          "Add your comment here..."
        );
      });

      // The proposed change has currently failing checks in the CI, so it cannot be merged
      test.fixme("merge and delete proposed change", async ({ page }) => {
        await page.goto("/proposed-changes");
        await page.getByText(pcNameEdit, { exact: true }).first().click();

        await test.step("ensure the checks are fine", async () => {
          await expect(page.getByTestId("checks-tab").getByTestId("Loading...")).toBeHidden();
          await page.getByText("Checks").click();

          // Reload page until we have successful checks
          while (
            (await page.getByText("Retry all").isVisible()) &&
            (await page.getByTestId("validator-success").isHidden())
          ) {
            await page.reload();
          }
        });

        await test.step("merge proposed change and update UI", async () => {
          await page.getByTestId("proposed-change-action-button-select").click();
          await page.getByRole("option", { name: "Merge" });
          await expect(page.getByText("Proposed changes merged successfully!")).toBeVisible();
          await expect(page.getByText("Statemerged")).toBeVisible();
        });

        await test.step("not able to edit proposed change", async () => {
          await expect(page.getByRole("button", { name: "Approve" })).toBeDisabled();
          await expect(page.getByTestId("proposed-change-action-button-select")).toBeDisabled();
          await expect(page.getByTestId("edit-button")).toBeDisabled();
        });

        await test.step("delete proposed change", async () => {
          await page.goto("/proposed-changes?pr_state=close");
          await page.getByTestId(`actions-row-${pcName}`).first().click();
          await page.getByTestId("delete-row-button").click();
          await expect(page.getByTestId("modal-delete")).toBeVisible();
          await page.getByTestId("modal-delete-confirm").click();
          await expect(page.getByText(`Proposed changes ${pcNameEdit} deleted`)).toBeVisible();
        });
      });
    });
  });
});
