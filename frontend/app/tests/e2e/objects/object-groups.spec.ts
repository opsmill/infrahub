import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("Object groups update", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("object-groups");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should contain initial values and update them", async ({ page }) => {
    await test.step("access the tags and create a new one", async () => {
      await page.goto(`/objects/BuiltinTag?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("link", { name: "blue" })).toBeVisible();
      await expect(page.getByTestId("create-object-button")).toBeVisible();
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Name *").fill("group-tag");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Tag created")).toBeVisible();
    });

    await test.step("go to the new tag", async () => {
      await page.getByRole("link", { name: "group-tag" }).click();
      await page.getByTestId("object-details-menu").click();
      await page.getByRole("menuitem", { name: "Groups" }).click();
      await expect(page.getByRole("heading", { name: "Manage groups", exact: true })).toBeVisible();
      await expect(page.getByText("There are no groups to display")).toBeVisible();
    });

    await test.step("open groups manager", async () => {
      await page.getByTestId("open-group-form-button").click();
    });

    await test.step("add groups to an object", async () => {
      await page.getByLabel("Add groups *").click();
      await page.getByRole("option", { name: "arista_devices" }).click();
      await page.getByRole("option", { name: "backbone_interfaces" }).click();
      await page.getByLabel("Add groups *").click(); // to close the combobox
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("2 groups added")).toBeVisible();
      await expect(page.getByText("2 groups added")).toBeHidden();
    });

    await test.step("auto-generated toggle button not visible if there is no auto-generated groups", async () => {
      await expect(page.getByRole("button", { name: "auto-generated" })).not.toBeVisible();
    });

    await test.step("new groups are visible in groups manager", async () => {
      await expect(page.getByRole("link", { name: "arista_devices" })).toBeVisible();
      await expect(page.getByRole("link", { name: "backbone_interfaces" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Standard Group" }).first()).toBeVisible();
    });

    await test.step("filter groups", async () => {
      await page.getByPlaceholder("filter groups...").fill("ari");
      await expect(page.getByRole("link", { name: "arista_devices" })).toBeVisible();
      await expect(page.getByRole("link", { name: "backbone_interfaces" })).not.toBeVisible();

      await page.getByPlaceholder("filter groups...").fill("");
      await expect(page.getByRole("link", { name: "arista_devices" })).toBeVisible();
      await expect(page.getByRole("link", { name: "backbone_interfaces" })).toBeVisible();
    });

    await test.step("leave arista_devices group", async () => {
      await page.getByTestId("leave-group-button").first().click();
      await expect(page.getByRole("heading", { name: "Leave Group" })).toBeVisible();
      await expect(
        page.getByText("Are you sure you want to leave group arista_devices?")
      ).toBeVisible();
      await page.getByTestId("modal-delete-confirm").click();
    });

    await test.step("arista_devices group is not visible in groups manager", async () => {
      await expect(page.getByRole("link", { name: "backbone_interfaces" })).toBeVisible();
      await expect(page.getByRole("link", { name: "arista_devices" })).not.toBeVisible();
    });

    await test.step("add group form default values is visible", async () => {
      await page.getByTestId("open-group-form-button").click();
      await expect(page.getByText("backbone_interfaces×")).toBeVisible();
      await expect(page.getByText("arista_devices×")).not.toBeVisible();
    });
  });
});
