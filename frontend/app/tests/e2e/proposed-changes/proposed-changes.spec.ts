import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { createBranch, deleteBranch } from "../../utils";

test.describe("/proposed-changes", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test.describe("when not logged in", () => {
    test("should not be able to create a proposed changes", async ({ page }) => {
      await page.goto("/proposed-changes");

      await expect(page.getByRole("heading", { name: "Proposed changes" })).toBeVisible();
      await expect(page.getByTestId("add-proposed-changes-button")).toBeDisabled();
    });
  });

  test.describe("when logged in as Admin", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("allow to create a proposed change", async ({ page }) => {
      await page.goto("/proposed-changes");

      await expect(page.getByRole("heading", { name: "Proposed changes" })).toBeVisible();
      await expect(page.getByTestId("add-proposed-changes-button")).toBeEnabled();
      await page.getByTestId("add-proposed-changes-button").click();
      await expect(page.getByRole("heading", { name: "Create a proposed change" })).toBeVisible();
    });

    test("display validation errors when form is submitted with wrong value", async ({ page }) => {
      await page.goto("/proposed-changes/new");

      await expect(page.getByRole("heading", { name: "Create a proposed change" })).toBeVisible();
      await page.getByRole("button", { name: "Create proposed change" }).click();
      await expect(page.getByLabel("Name *").locator("..")).toContainText("Required");
      await expect(page.getByText("Source Branch *").locator("..")).toContainText("Required");
    });

    test.describe("Create, edit and merge proposed change", async () => {
      test.describe.configure({ mode: "serial" });

      const pcName = "pc-e2e";
      const pcNameEdit = "pc-e2e-edit";
      const pcBranchName = "main-copy-for-pc-e2e";

      test.beforeAll(async ({ browser }) => {
        const page = await browser.newPage();
        await page.goto("/proposed-changes");
        await createBranch(page, pcBranchName);
        await page.close();
      });

      test.afterAll(async ({ browser }) => {
        const page = await browser.newPage();
        await page.goto("/proposed-changes");
        await deleteBranch(page, pcBranchName);
        await page.close();
      });

      test("create new proposed change", async ({ page }) => {
        await page.goto("/proposed-changes/new");
        await expect(page.getByText("Create a proposed Change")).toBeVisible();

        await page.getByLabel("Source Branch *").click();
        await page.getByRole("option", { name: pcBranchName }).click();
        await page.getByLabel("Name *").fill(pcName);
        await page.getByTestId("codemirror-editor").getByRole("textbox").fill("My description");
        await page.getByTestId("select-open-option-button").click();
        await page.getByRole("option", { name: "Architecture Team" }).click();
        await page.getByRole("option", { name: "Crm Synchronization" }).click();
        await page.getByTestId("select-open-option-button").click();

        await page.getByRole("button", { name: "Create proposed change" }).click();
        await expect(page.getByText("Proposed change created")).toBeVisible();
      });

      test("display and edit proposed change", async ({ page }) => {
        await page.goto("/proposed-changes");

        await test.step("display created proposed change details", async () => {
          await page.getByText(pcName, { exact: true }).click();
          await expect(page.getByText("Source branch" + pcBranchName)).toBeVisible();
          await expect(page.getByText("Stateopen")).toBeVisible();
        });

        await test.step("edit proposed change reviewers", async () => {
          await page.getByTestId("edit-button").click();
          await page.getByLabel("Name").fill(pcNameEdit);
          await page
            .getByTestId("side-panel-container")
            .getByTestId("codemirror-editor")
            .getByRole("textbox")
            .fill("My description edit");
          await page.getByTestId("multi-select-input").getByText("Crm Synchronization").click();
          await page.getByLabel("Reviewers").click(); // Hack to close Reviewers select option list
          await page.getByRole("button", { name: "Save" }).click();
          await expect(page.getByText("ProposedChange updated")).toBeVisible();

          await expect(page.getByRole("heading", { name: pcNameEdit, exact: true })).toBeVisible();
          await expect(page.getByTestId("pc-description")).toContainText("My description edit");
          await expect(page.getByText("ReviewersAT")).toBeVisible();
        });
      });

      test("add a comment on overview tab", async ({ page }) => {
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

      test.fixme("merged proposed change", async ({ page }) => {
        await page.goto("/proposed-changes");
        await page.getByText(pcNameEdit, { exact: true }).first().click();

        await test.step("merge proposed change and update UI", async () => {
          await page.getByRole("button", { name: "Merge" }).click();
          await expect(page.getByText("Proposed changes merged successfully!")).toBeVisible();
          await expect(page.getByText("Statemerged")).toBeVisible();
        });

        await test.step("not able to edit proposed change", async () => {
          await expect(page.getByRole("button", { name: "Approve" })).toBeDisabled();
          await expect(page.getByRole("button", { name: "Merge" })).toBeDisabled();
          await expect(page.getByRole("button", { name: "Close" })).toBeDisabled();
          await expect(page.getByTestId("edit-button")).toBeDisabled();
        });
      });

      test("delete proposed change", async ({ page }) => {
        await page.goto("/proposed-changes");
        await page
          .getByRole("link", { name: `${pcNameEdit} 0 ${pcBranchName}` })
          .locator("../..")
          .getByTestId("actions-row-button")
          .click();
        await page.getByTestId("delete-row-button").click();
        await expect(page.getByTestId("modal-delete")).toBeVisible();
        await page.getByTestId("modal-delete-confirm").click();
        await expect(page.getByText(`Proposed changes '${pcNameEdit}' deleted`)).toBeVisible();
      });
    });
  });
});
