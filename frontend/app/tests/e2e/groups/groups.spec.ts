import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, saveScreenshotForDocs } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/objects/CoreGroup - Generic Group Object.", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("groups");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("1. Create a new Standard Group", async ({ page }) => {
    await page.goto(`/objects/CoreGroup?branch=${BRANCH_NAME}`);
    await expect(
      page.getByTestId("object-items").getByRole("link", { name: "arista_devices" })
    ).toBeVisible();

    await test.step("fill and submit form for new group", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Standard Group" }).click();

      await page.getByLabel("Name *").fill("TagConfigGroup");
      await saveScreenshotForDocs(page, "group_tagconfig_grp_new_grp");

      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("StandardGroup created")).toBeVisible();
    });
  });

  test("2. Add members to Standard Group", async ({ page }) => {
    await page.goto(`/objects/CoreGroup?branch=${BRANCH_NAME}`);

    await test.step("add members to Standard Group", async () => {
      await page.getByLabel("Hierarchy tree").getByText("TagConfigGroup").click();
      await page.getByText("Members0").click();
      await page.getByTestId("open-relationship-form-button").click();
      await page.getByRole("combobox", { name: "Kind" }).click();
      await page.getByRole("option", { name: "Tag Builtin" }).click();
      await expect(page.getByRole("option", { name: "Tag Builtin" })).toBeHidden();
      await page.getByLabel("Tag", { exact: true }).click();
      await page.getByRole("option", { name: "blue" }).click();

      await saveScreenshotForDocs(page, "group_tagconfig_grp_adding_members");

      await page.getByRole("button", { name: "Save" }).click();
      await page.getByTestId("close-alert").click();

      await page.getByTestId("open-relationship-form-button").click();
      await page.getByRole("combobox", { name: "Kind" }).click();
      await page.getByRole("option", { name: "Tag Builtin" }).click();
      await page.getByLabel("Tag", { exact: true }).click();
      await page.getByRole("option", { name: "red" }).click();
      await expect(page.getByRole("option", { name: "red" })).not.toBeVisible();
      await page.getByRole("button", { name: "Save" }).click();
      await page.getByText("Members2").click();

      await saveScreenshotForDocs(page, "group_tagconfig_grp_new_members");
    });
  });
});
