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
      await Promise.all([
        page.waitForResponse((response) => {
          const reqData = response.request().postDataJSON();
          const status = response.status();

          return reqData?.operationName === "BuiltinTag" && status === 200;
        }),
        page.goto("/objects/BuiltinTag"),
      ]);
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Name *").fill(NEW_TAG);
      await page.getByRole("button", { name: "Create" }).click();
    });

    await test.step("go to the new tag", async () => {
      await page.getByRole("link", { name: NEW_TAG }).click();
      await page.getByRole("button", { name: "Manage groups" }).click();
      await expect(page.getByText("Empty list")).toBeVisible();
    });

    await test.step("update the groups #1", async () => {
      await page.getByTestId("select-open-option-button").click();
      await page.getByText("Arista Devices").click();
      await page.getByText("Cisco Devices").click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Group updated")).toBeVisible();
      await page.getByRole("button", { name: "Manage groups" }).click();
      await expect(
        page.getByTestId("multi-select-input").getByText("Arista Devices")
      ).toBeVisible();
      await expect(page.getByTestId("multi-select-input").getByText("Cisco Devices")).toBeVisible();
    });

    await test.step("update the groups #2", async () => {
      await page.locator("span").filter({ hasText: "Cisco Devices" }).locator("svg").click();
      await expect(
        page.getByTestId("multi-select-input").getByText("Arista Devices")
      ).toBeVisible();
      await expect(
        page.getByTestId("multi-select-input").getByText("Cisco Devices")
      ).not.toBeVisible();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Group updated")).toBeVisible();
      await page.getByRole("button", { name: "Manage groups" }).click();
      await expect(
        page.getByTestId("multi-select-input").getByText("Arista Devices")
      ).toBeVisible();
      await expect(
        page.getByTestId("multi-select-input").getByText("Cisco Devices")
      ).not.toBeVisible();
    });
  });
});
