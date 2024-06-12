import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("Getting started with Infrahub - Integration with Git", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("1. Generate the configuration of a device", async ({ page }) => {
    await page.goto("/");

    await test.step(" Create a new branch update-ethernet1", async () => {
      await page.getByTestId("create-branch-button").click();
      await page.getByLabel("New branch name").fill("update-ethernet1");
      await page.getByLabel("Sync with Git").click();
      await saveScreenshotForDocs(page, "tutorial_6_branch_creation");
      await page.getByRole("button", { name: "Create" }).click();

      await expect(page.getByTestId("branch-select-menu")).toContainText("update-ethernet1");
    });

    await test.step("go to interface Ethernet 1 for atl1-edge1", async () => {
      await page.getByRole("link", { name: "All Device(s)" }).click();
      await expect(page.getByText("Generic Device object")).toBeVisible();
      await page.getByRole("link", { name: "atl1-edge1" }).click();
      await page.getByText("Interfaces15").click();
      await page.getByRole("link", { name: "Connected to atl1-edge2 Ethernet1" }).click();
    });

    await test.step("Update the interface Ethernet 1 for atl1-edge1", async () => {
      await page.getByRole("button", { name: "Edit" }).click();
      await page.getByLabel("Description").fill("New description in the branch");
      await saveScreenshotForDocs(page, "tutorial_6_interface_update");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.locator("#alert-success-updated")).toContainText("InterfaceL3 updated");
    });
  });

  // test("Update the Jinja2 template in GitHub", async ({ page }) => {
  //   // not currently E2E testable
  // });
});
