import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("object dropdown creation", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should open the creation form and open the tag option creation form", async ({ page }) => {
    // Go to home page
    await page.goto("/");

    await Promise.all([
      page.waitForResponse((response) => {
        const reqData = response.request().postDataJSON();
        const status = response.status();

        return reqData?.operationName === "InfraDevice" && status === 200;
      }),

      // Open all devices
      page.getByRole("link", { name: "All Device(s)" }).click(),
    ]);

    // Open creation form
    await page.getByTestId("create-object-button").click();

    // Open tags options
    await page
      .getByTestId("select-container")
      .nth(6)
      .getByTestId("select-open-option-button")
      .click();

    // Add new option
    await page.getByRole("option", { name: "Add Tag" }).click();

    // Assert form content is visible
    await expect(page.getByText("Create Tag")).toBeVisible();
    await expect(page.getByRole("button", { name: "Create" })).toBeVisible();

    // Create a new tag
    await page.getByLabel("Create TagmainStandard Tag").locator("#Name").click();
    await page.getByLabel("Create TagmainStandard Tag").locator("#Name").fill("new-tag");
    await page.getByLabel("Create TagmainStandard Tag").locator("#Name").press("Tab");
    await page
      .getByLabel("Create TagmainStandard Tag")
      .locator("#Description")
      .fill("New tag description");

    // Submit
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByText("Tag created")).toBeVisible();

    // Closes the form
    await page.getByRole("button", { name: "Cancel" }).click();
  });
});
