import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

const NEW_DEVICE_NAME = "New device";
const EXISTING_TAG = "blue";
const EXISTING_TAG_2 = "red";
const NEW_TAG_NAME = "New tag";
const NEW_TAG_NAME_2 = "New tag 2";

test.describe("Verify multi select behaviour", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("Create a new device with exisiting tags + a new tag, and verify the multi select values", async ({
    page,
  }) => {
    // Go to devices
    await page.goto("/");
    await page.getByRole("link", { name: "All Device(s)" }).click();

    // Create device
    await page.getByTestId("create-object-button").click();
    await page.getByLabel("Name *").fill(NEW_DEVICE_NAME);
    await page.getByLabel("Type *").click();
    await page.getByLabel("Type *").fill("type");
    await page
      .locator("div:below(:text('Site *'))")
      .first()
      .getByTestId("select-open-option-button")
      .click();
    await page.getByRole("option", { name: "atl1" }).click();

    // Add existing tag
    await page
      .locator("div:below(:text('Tags'))")
      .first()
      .getByTestId("select-open-option-button")
      .click();
    await page.getByRole("option", { name: EXISTING_TAG }).click();

    await expect(
      page.getByTestId("side-panel-container").getByText(EXISTING_TAG).first()
    ).toBeVisible();

    // Create new tag
    await page.getByText("Add Tag").click();
    await page.getByLabel("Create TagmainStandard Tag").locator("#Name").click();
    await page.getByLabel("Create TagmainStandard Tag").locator("#Name").fill(NEW_TAG_NAME);

    // Submit creation and check values
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.locator("#alert-success-Tag-created")).toContainText("Tag created");
    await expect(page.getByText(NEW_TAG_NAME)).toBeVisible();
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.locator("#alert-success-Device-created")).toContainText("Device created");
    //Search new object
    await page.getByPlaceholder("Search anywhere").click();
    await page
      .getByTestId("search-anywhere")
      .getByPlaceholder("Search anywhere")
      .fill(NEW_DEVICE_NAME);

    await page.getByRole("option", { name: `${NEW_DEVICE_NAME}Device Description` }).click();

    // Verify values
    await expect(page.getByRole("link", { name: "blue" })).toBeVisible();
    await expect(page.getByRole("link", { name: NEW_TAG_NAME })).toBeVisible();

    // Open form and check values
    await page.getByRole("button", { name: "Edit" }).click();
    await expect(
      page.getByTestId("side-panel-container").getByText(EXISTING_TAG).first()
    ).toBeVisible();
    await expect(
      page.getByTestId("side-panel-container").getByText(NEW_TAG_NAME).first()
    ).toBeVisible();

    // Add existing tag #2
    await page
      .locator("div:below(:text('Tags'))")
      .first()
      .getByTestId("select-open-option-button")
      .click();
    await page.getByTestId("side-panel-container").getByText(EXISTING_TAG_2).click();
    await expect(
      page.getByTestId("side-panel-container").getByText(EXISTING_TAG_2).first()
    ).toBeVisible();

    // Add new tag #2
    await page.getByText("Add Tag").click();
    await page.getByLabel("Create TagmainStandard Tag").locator("#Name").fill(NEW_TAG_NAME_2);
    await page.getByRole("button", { name: "Create" }).click();

    await expect(
      page.getByTestId("side-panel-container").getByText(EXISTING_TAG).first()
    ).toBeVisible();
    await expect(
      page.getByTestId("side-panel-container").getByText(NEW_TAG_NAME).first()
    ).toBeVisible();
    await expect(
      page.getByTestId("side-panel-container").getByText(NEW_TAG_NAME_2).first()
    ).toBeVisible();

    // Save and verify values
    await page.getByRole("button", { name: "Save" }).click();

    await expect(page.locator("#alert-success-updated")).toContainText("Device updated");

    await expect(page.getByText(NEW_TAG_NAME_2)).toBeVisible();
  });
});
