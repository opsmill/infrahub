import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/proposed-changes diff data", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should verify the diff data with conflicts", async ({ page }) => {
    await test.step("create a new proposed change with reviewers", async () => {
      await page.goto("/proposed-changes");
      await page.getByTestId("add-proposed-changes-button").click();
      await page.getByLabel("Source Branch *").click();
      await page.getByRole("option", { name: "den1-maintenance-conflict" }).click();
      await page.getByLabel("Name *").fill("conflict-test");
      await page.getByLabel("Reviewers").click();
      await page.getByRole("option", { name: "Admin" }).click();
      await page.getByLabel("Reviewers").click();
      await page.getByRole("button", { name: "Open", exact: true }).click();
      await expect(page.getByText("Proposed change created")).toBeVisible();
      await page.getByText("Data").click();
    });

    await test.step("trigger the diff update", async () => {
      await page.getByRole("button", { name: "Refresh" }).click();
      await expect(page.getByText("Diff updated!")).toBeVisible();
    });

    await test.step("check diff data", async () => {
      await expect(page.getByText("UpdatedInterfaceL3Ethernet1")).toBeVisible();
      await expect(page.getByRole('link', { name: 'Ethernet1' })).toBeVisible();
      await expect(page.getByText("UpdatedDeviceden1-edge1")).toBeVisible();
      await expect(page.getByRole("link", { name: "den1-edge1" })).toBeVisible();
      await page.getByText("UpdatedInterfaceL3Ethernet1").click();
      await expect(
        page.getByText("UpdatedInterfaceL3Ethernet1 main den1-maintenance-")
      ).toBeVisible();
      await page.getByLabel("diff tree").getByText("den1-edge1").click();
      await page
        .getByText(
          "main den1-maintenance-conflictstatusConflictactiveprovisioningmaintenanceChoose"
        )
        .click();
      const hash = await page.evaluate(() => window.location.hash);
      const highlightedNodeDiff = page.locator(`id=${hash.slice(1)}`);
      await expect(highlightedNodeDiff).toBeInViewport();
      await expect(highlightedNodeDiff).toContainClass("ring-2 ring-custom-blue-500");
    });

    await test.step("resolve conflict", async () => {
      await expect(
        page.getByText("Choose the branch to resolve the conflict:mainden1-maintenance-conflict")
      ).toBeVisible();
      await page.getByRole("checkbox", { name: "main", exact: true }).click();
      await expect(page.getByText("Conflict marked as resolved")).toBeVisible();
    });
  });

  test("should comment a proposed changes", async ({ page }) => {
    await test.step("access proposed change diff tab", async () => {
      await page.goto("/proposed-changes");
      await page.getByRole("link", { name: "conflict-test" }).click();
      await expect(page.getByRole("heading", { name: "conflict-test" })).toBeVisible();
      await page.getByText("Data").click();
      await expect(page.getByRole("button", { name: "Refresh diff" })).toBeVisible();
    });

    await test.step("comment proposed changes", async () => {
      await page.locator("span").filter({ hasText: "UpdatedDeviceden1-edge1" }).hover();
      await page
        .locator("span")
        .filter({ hasText: "UpdatedDeviceden1-edge1" })
        .getByTestId("data-diff-add-comment")
        .click();
      await expect(page.getByText("Add a comment")).toBeVisible();
      await page.getByRole("textbox").click();
      await page.getByRole("textbox").fill("Some comment ");
      await page.getByRole("button", { name: "Comment", exact: true }).click();
      await expect(page.getByTestId("comment").getByText("AAdmin")).toBeVisible();

      await expect(page.getByLabel("Resolve thread")).not.toBeChecked();
      await page.getByLabel("Resolve thread").click();
      await page.getByRole("button", { name: "Confirm", exact: true }).click();
      await expect(page.getByLabel("Resolved")).toBeChecked();
    });
  });

  test("should delete the proposed change", async ({ page }) => {
    await page.goto("/proposed-changes");
    await page.getByTestId("actions-row-button-conflict-test").click();
    await page.getByTestId("delete-row-button").click();
    await expect(page.getByTestId("modal-delete")).toBeVisible();
    await page.getByTestId("modal-delete-confirm").click();
    await expect(page.getByText("Proposed changes conflict-test deleted")).toBeVisible();
  });
});
