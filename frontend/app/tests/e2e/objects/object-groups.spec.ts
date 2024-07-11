import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

const NEW_TAG = "group-tag";

test.describe("Object groups update", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should contain initial values and update them", async ({ page }) => {
    await test.step("access the tags and create a new one", async () => {
      await page.goto("/objects/BuiltinTag");
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Name *").fill(NEW_TAG);
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Tag created")).toBeVisible();
    });

    await test.step("go to the new tag", async () => {
      await page.getByRole("link", { name: NEW_TAG }).click();
      await page.getByTestId("manage-groups").click();
      await expect(page.getByRole("heading", { name: "Manage groups", exact: true })).toBeVisible();
      await expect(page.getByText("There are no groups to display")).toBeVisible();
    });

    await test.step("add groups to an object", async () => {
      await page.getByTestId("open-group-form-button").click();
      await expect(page.getByTestId("multi-select-input")).toContainText("Empty list");
      await page.getByTestId("select-open-option-button").click();
      await page.getByRole("option", { name: "arista_devices" }).click();
      await page.getByRole("option", { name: "backbone_interfaces" }).click();
      await page.getByTestId("select-open-option-button").click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("2 groups added")).toBeVisible();
    });

    await test.step("new groups are visible in groups manager", async () => {
      await expect(page.getByRole("link", { name: "arista_devices" })).toBeVisible();
      await expect(page.getByRole("link", { name: "backbone_interfaces" })).toBeVisible();
      await expect(page.getByRole("link", { name: "CoreStandardGroup" }).first()).toBeVisible();
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

    await test.step("add group form does not contains object groups", async () => {
      await page.getByTestId("open-group-form-button").click();
      await expect(page.getByTestId("multi-select-input")).toContainText("Empty list");
    });
  });
});
