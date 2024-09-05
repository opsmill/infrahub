import { test, expect } from "@playwright/test";
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

  test("should verify the diff data with conflicts", async ({ page }) => {
    await test.step("create a new proposed change with reviewers", async () => {
      await page.goto("/proposed-changes");
      await page.getByTestId("add-proposed-changes-button").click();
      await page.getByLabel("Source Branch *").click();
      await page.getByRole("option", { name: "den1-maintenance-conflict" }).click();
      await page.getByLabel("Name *").fill("conflict-test");
      await page.getByTestId("select-open-option-button").click();
      await page.getByRole("option", { name: "Admin" }).click();
      await page.getByRole("main").click();
      await page.getByRole("button", { name: "Create proposed change" }).click();
      await expect(page.getByText("Proposed change created")).toBeVisible();
      await page.getByText("Data").click();
    });

    // await test.step("trigger the diff update", async () => {
    //   await expect(page.getByText("We are computing the diff")).toBeVisible();
    //   await page.getByRole("button", { name: "Refresh" }).click();
    //   await expect(page.getByText("Diff updated!")).toBeVisible({ timeout: 5 * 60 * 1000 });
    // });

    await test.step("check diff data", async () => {
      await expect(page.getByText("UpdatedDeviceden1-edge1")).toBeVisible();
      await expect(page.getByText("UpdatedInterface L3Ethernet1")).toBeVisible();
      await page.getByText("UpdatedDeviceden1-edge1").click();
      await expect(page.getByText("status")).toBeVisible();
      await expect(page.getByText("active", { exact: true })).toBeVisible();
      await expect(page.getByText("maintenance", { exact: true }).first()).toBeVisible();
      await expect(page.getByText("statusConflict")).toBeVisible();
      await expect(
        page
          .locator("div")
          .filter({ hasText: /^activeprovisioning$/ })
          .nth(1)
      ).toBeVisible();
    });

    await test.step("resolve conflict", async () => {
      await page.getByRole("checkbox", { name: "main", exact: true }).click();
      await expect(page.getByText("Conflict marked as resovled")).toBeVisible();
    });

    await test.step("filter diff data", async () => {
      await page.getByRole("button", { name: "1" }).click();
      await expect(page.getByText("UpdatedDeviceden1-edge1")).toBeVisible();
      await expect(page.getByText("UpdatedInterface L3Ethernet1")).not.toBeVisible();
      await page.getByRole("button", { name: "1" }).click();
      await expect(page.getByText("UpdatedInterface L3Ethernet1")).toBeVisible();
    });
  });

  test("should approve a proposed changes", async ({ page }) => {
    await test.step("got to the proposed changes data tab", async () => {
      await page.goto("/proposed-changes");
      await page.getByRole("link", { name: "conflict-test" }).first().click();
      await expect(page.getByRole("cell", { name: "A", exact: true }).first()).toBeVisible();
      await expect(page.getByRole("cell", { name: "A", exact: true }).nth(1)).toBeVisible();
      await page.getByRole("button", { name: "Approve" }).click();
      await expect(page.getByText("Proposed change approved")).toBeVisible();
    });

    await test.step("check approval", async () => {
      await expect(page.getByRole("cell", { name: "A", exact: true }).nth(1)).toBeVisible();
      await expect(page.getByRole("cell", { name: "A", exact: true }).nth(2)).toBeVisible();
      await page.getByRole("link", { name: "Proposed changes", exact: true }).click();
      await expect(page.getByTestId("approved-icon")).toBeVisible();
    });
  });

  test("should comment a proposed changes", async ({ page }) => {
    await test.step("access proposed change diff tab", async () => {
      await page.goto("/proposed-changes");
      await page.getByRole("link", { name: "conflict-test" }).click();
      await expect(
        page.locator("header").filter({ hasText: "Proposed changesconflict-test" })
      ).toBeVisible();
      await page.getByText("Data").click();
      await expect(page.getByRole("button", { name: "Refresh diff" })).toBeVisible();
    });

    await test.step("comment proposed changes", async () => {
      await page.locator("span").filter({ hasText: "UpdatedInterface L3Ethernet1" }).hover();
      await page
        .locator("span")
        .filter({ hasText: "UpdatedInterface L3Ethernet1" })
        .getByTestId("data-diff-add-comment")
        .click();
      await page.getByRole("textbox").fill("test");
      await page.getByRole("button", { name: "Comment", exact: true }).click();
      await expect(page.getByText("AAdminless than a minute ago")).toBeVisible();
      await page.getByTestId("comment").getByText("test").click();
      await page.getByRole("button", { name: "Reply" }).click();
      await page.getByRole("textbox").fill("test 2");
      await page.getByRole("button", { name: "Comment", exact: true }).click();
      await expect(page.getByText("AAdminless than a minute agotest")).toBeVisible();
      await expect(page.getByLabel("Resolve thread")).not.toBeChecked();
      await page.getByLabel("Resolve thread").click();
      await page.getByRole("button", { name: "Confirm", exact: true }).click();
      await expect(page.getByLabel("Resolved")).toBeChecked();
    });
  });

  test("should delete proposed changes", async ({ page }) => {
    await page.goto("/proposed-changes");
    await page
      .getByRole("link", { name: "conflict-test" })
      .first()
      .locator("../..")
      .getByTestId("delete-row-button")
      .click();
    await expect(page.getByTestId("modal-delete")).toBeVisible();
    await page.getByTestId("modal-delete-confirm").click();
    await expect(page.getByText("Proposed changes 'conflict-test' deleted")).toBeVisible();
  });
});
