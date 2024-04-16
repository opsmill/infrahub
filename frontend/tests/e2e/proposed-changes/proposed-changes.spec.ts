import { expect, Page, test } from "@playwright/test";
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
    test.fixme("should not be able to create a proposed changes", async ({ page }) => {
      await page.goto("/proposed-changes");

      await expect(page.getByText("ProposedChange")).toBeVisible();
      await expect(page.getByTestId("add-proposed-changes-button")).toBeDisabled();
    });
  });

  test.describe("when logged in as Admin", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test.fixme("should be able to create a proposed changes", async ({ page }) => {
      await page.goto("/proposed-changes");

      await expect(page.getByText("ProposedChange")).toBeVisible();
      await expect(page.getByTestId("add-proposed-changes-button")).toBeEnabled();
      await page.getByTestId("add-proposed-changes-button").click();
      await expect(page.getByText("Create Proposed Changes")).toBeVisible();
    });

    test.fixme(
      "Should display an error message when proposed change create fails",
      async ({ page }) => {
        await page.goto("/proposed-changes");

        await expect(page.getByText("ProposedChange")).toBeVisible();
        await expect(page.getByTestId("add-proposed-changes-button")).toBeEnabled();
        await page.getByTestId("add-proposed-changes-button").click();
        await expect(page.getByText("Create Proposed Changes")).toBeVisible();
        await page.getByLabel("Name *").fill("test-create-fail");
        await page.getByRole("button", { name: "Create" }).click();
        await expect(page.locator("#alert-error")).toContainText(
          "Field 'CoreProposedChangeCreateInput.source_branch' of required type 'TextAttributeInput!' was not provided."
        );
      }
    );

    test.describe("Create, edit and merge proposed change", async () => {
      test.describe.configure({ mode: "serial" });

      let page: Page;
      const pcName = "pc-e2e";
      const pcBranchName = "main-copy-for-pc-e2e";

      test.beforeAll(async ({ browser }) => {
        page = await browser.newPage();
        await page.goto("/proposed-changes");
        await createBranch(page, pcBranchName);
      });

      test.afterAll(async () => {
        await deleteBranch(page, pcBranchName);
      });

      test.fixme("create new proposed change", async () => {
        await page.getByTestId("add-proposed-changes-button").click();
        await expect(page.getByText("Create Proposed Change")).toBeVisible();
        await page.getByLabel("Name *").fill(pcName);
        await page
          .locator("div:below(#Name)")
          .first()
          .getByTestId("select-open-option-button")
          .click();
        await expect(page.getByRole("option").nth(1)).toContainText(pcName); // last created branch should appear first
        await page.getByRole("option", { name: pcBranchName }).click();
        await page.getByRole("button", { name: "Create" }).click();
        await expect(page.getByText("ProposedChange created")).toBeVisible();
      });

      test.fixme("display and edit proposed change", async () => {
        await test.step("display created proposed change details", async () => {
          await expect(page.getByText("Name" + pcName)).toBeVisible();
          await expect(page.getByText("Source branch" + pcBranchName)).toBeVisible();
          await expect(page.getByText("Stateopen")).toBeVisible();
        });

        await test.step("edit proposed change reviewers", async () => {
          await page.getByRole("button", { name: "Edit" }).click();
          await page
            .getByText("Empty list")
            .locator("..")
            .getByTestId("select-open-option-button")
            .click();
          await page.getByRole("option", { name: "Architecture Team" }).click();
          await page.getByText("CoreThread").click(); // Hack to close Reviewers select option list
          await page.getByRole("button", { name: "Save" }).click();
          await expect(page.getByText("ProposedChange updated")).toBeVisible();

          await expect(page.getByText("ReviewersArchitecture Team", { exact: true })).toBeVisible();
        });
      });

      test.fixme("merged proposed change", async () => {
        await test.step("merge proposed change and update UI", async () => {
          await page.getByRole("button", { name: "Merge" }).click();
          await expect(page.getByText("Proposed changes merged successfully!")).toBeVisible();
          await expect(page.getByText("Statemerged")).toBeVisible();
        });

        await test.step("not able to edit proposed change", async () => {
          await expect(page.getByRole("button", { name: "Merge" })).toBeDisabled();
          await expect(page.getByRole("button", { name: "Edit" })).toBeDisabled();
        });
      });

      test.fixme("delete proposed change", async () => {
        await page.getByRole("link", { name: "Proposed Changes" }).click();
        await page.getByRole("list").getByText(pcName).first().hover();
        await page.locator("[data-testid='delete-proposed-change-button']:visible").click();
        await expect(page.getByTestId("modal-delete")).toBeVisible();
        await page.getByTestId("modal-delete-confirm").click();
        await expect(page.getByText("Proposed changes deleted")).toBeVisible();
      });
    });
  });
});
