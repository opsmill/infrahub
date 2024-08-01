import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/proposed-changes diff data", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should create a new proposed changes", async ({ page }) => {
    await page.goto("/proposed-changes");

    await test.step("create a new proposed change", async () => {
      await page.getByTestId("add-proposed-changes-button").click();
      await expect(page.getByText("Create Proposed Change")).toBeVisible();
      await page.getByLabel("Name *").fill("pc-data-diff");
      await page.getByLabel("Source Branch *").click();
      await page.getByRole("option", { name: "atl1-delete-upstream" }).click();
      await page.getByRole("button", { name: "Create" }).click();
      await expect(page.getByText("Proposed change created")).toBeVisible();
    });

    await test.step("display created proposed change details", async () => {
      await expect(page.getByText("Namepc-data-diff")).toBeVisible();
      await expect(page.getByText("Source branchatl1-delete-upstream")).toBeVisible();
      await expect(page.getByText("Stateopen")).toBeVisible();
    });

    await test.step("go to Tasks tab and do not see related node information", async () => {
      await page.getByLabel("Tabs").getByText("Tasks").click();
      await expect(page.locator("thead")).not.toContainText("Related node");
    });

    await test.step("go to Data tab and open comment form", async () => {
      await page.getByLabel("Tabs").getByText("Data").click();
      await expect(page.getByText("Just a moment")).not.toBeVisible();
      await expect(page.getByText("RemovedInfraCircuit", { exact: true }).first()).toBeVisible();
      await page.getByText("RemovedInfraCircuit", { exact: true }).first().hover();
      await expect(page.getByTestId("data-diff-add-comment").first()).toBeVisible();
      await page.getByTestId("data-diff-add-comment").first().click();
      await expect(page.getByText("Conversation")).toBeVisible();
    });

    await test.step("add first comment", async () => {
      await page.getByTestId("codemirror-editor").getByRole("textbox").fill("first is comment");
      await page.getByRole("button", { name: "Comment", exact: true }).click();
      await expect(page.getByText("Reply")).toBeVisible();
      await expect(page.getByTestId("thread").getByTestId("comment")).toContainText(
        "first is comment"
      );
      await expect(page.getByTestId("comments-count")).toContainText("1");
    });

    const thread = page.getByTestId("thread");

    await test.step("reply to first comment", async () => {
      await thread.getByRole("button", { name: "Reply" }).click();
      await thread.getByTestId("codemirror-editor").getByRole("textbox").fill("second is reply");
      await page.getByRole("button", { name: "Comment", exact: true }).click();
      await expect(page.getByText("Reply")).toBeVisible();
      await expect(page.getByText("second is reply")).toBeVisible();
      await expect(page.getByTestId("comments-count")).toContainText("2");
    });

    await test.step("start then cancel new comment", async () => {
      await page.getByRole("button", { name: "Reply" }).click();
      await expect(thread.getByTestId("codemirror-editor")).toBeVisible();
      await page.getByRole("button", { name: "Cancel" }).click();
      await expect(thread.getByTestId("codemirror-editor")).toBeHidden();
    });

    await test.step("Resolve thread", async () => {
      await thread.getByLabel("Resolve thread").click();
      await expect(page.getByRole("heading", { name: "Confirm" })).toBeVisible();
      await page.getByRole("button", { name: "Confirm" }).click();
      await expect(thread.getByText("Resolved")).toBeVisible();
    });

    await test.step("add comment when thread is resolved", async () => {
      await thread.getByRole("button", { name: "Reply" }).click();
      await thread.getByTestId("codemirror-editor").getByRole("textbox").fill("third resolved");
      await thread.getByRole("button", { name: "Comment", exact: true }).click();
      await expect(thread.getByTestId("comment").nth(2).getByText("third resolved")).toBeVisible();
      await expect(page.getByTestId("comments-count").getByText("3")).toBeVisible();
    });
  });

  test("should delete proposed changes", async ({ page }) => {
    await page.goto("/proposed-changes");
    await page
      .getByRole("link", { name: "pc-data-diff 0 atl1-delete-" })
      .first()
      .locator("../..")
      .getByTestId("delete-row-button")
      .click();
    await expect(page.getByTestId("modal-delete")).toBeVisible();
    await page.getByTestId("modal-delete-confirm").click();
    await expect(page.getByText("Proposed changes 'pc-data-diff' deleted")).toBeVisible();
  });
});
