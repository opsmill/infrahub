import { test, expect } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../utils";

test.describe("/proposed-changes diff data", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should create a new proposed changes", async ({ page }) => {
    await page.goto("/proposed-changes");
    await page.getByTestId("add-proposed-changes-button").click();

    // Form
    await expect(page.getByText("Create Proposed Changes")).toBeVisible();
    await page.getByLabel("Name *").fill("pc-data-diff");
    await page.locator("div:below(#Name)").first().getByTestId("select-open-option-button").click();
    await page.getByRole("option", { name: "atl1-delete-transit" }).click();
    await page.getByRole("button", { name: "Create" }).click();

    // After submit
    await expect(page.getByText("ProposedChange created")).toBeVisible();

    await expect(page.getByText("Namepc-data-diff")).toBeVisible();
    await expect(page.getByText("Source branchatl1-delete-transit")).toBeVisible();
    await expect(page.getByText("Stateopen")).toBeVisible();

    await page.getByLabel("Tabs").getByText("Data").click();
    await page.getByText("InfraCircuit").first().hover();
    await page.getByTestId("data-diff-add-comment").first().click();

    // form
    await expect(page.getByText("Conversation")).toBeVisible();

    // first comment
    await page.getByTestId("codemirror-editor").getByRole("textbox").fill("first is comment");
    await page.getByRole("button", { name: "Comment" }).click();
    const thread = await page.getByTestId("thread");
    await expect(thread.getByTestId("comment")).toContainText("first is comment");
    await expect(page.getByTestId("comments-count")).toContainText("1");

    // reply
    await thread.getByRole("button", { name: "Reply" }).click();
    await thread.getByTestId("codemirror-editor").getByRole("textbox").fill("second is reply");
    await page.getByRole("button", { name: "Comment" }).click();
    await expect(thread.getByTestId("comment").nth(1)).toContainText("second is reply");
    await expect(page.getByTestId("comments-count")).toContainText("2");

    // cancel reply
    await page.getByRole("button", { name: "Reply" }).click();
    await expect(thread.getByTestId("codemirror-editor")).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(thread.getByTestId("codemirror-editor")).toBeHidden();

    // Resolve
    await thread.getByLabel("Resolve thread").click();
    await expect(page.getByRole("heading", { name: "Confirm" })).toBeVisible();
    await page.getByRole("button", { name: "Confirm" }).click();
    await expect(thread.getByText("Resolved")).toBeVisible();

    // third comment
    await thread.getByRole("button", { name: "Reply" }).click();
    await thread.getByTestId("codemirror-editor").getByRole("textbox").fill("third resolved");
    await thread.getByRole("button", { name: "Comment" }).click();
    await expect(thread.getByTestId("comment").nth(2)).toContainText("third resolved");
    await expect(page.getByTestId("comments-count")).toContainText("3");
  });

  test("should delete proposed changes", async ({ page }) => {
    await page.goto("/proposed-changes");
    await page.getByText("pc-data-diff").first().hover();
    await page.locator("[data-testid='delete-proposed-change-button']:visible").click();
    await expect(page.getByTestId("modal-delete")).toBeVisible();
    await page.getByTestId("modal-delete-confirm").click();
    await expect(page.getByText("Proposed changes deleted")).toBeVisible();
  });
});
