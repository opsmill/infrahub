import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("Getting started with Infrahub - Data lineage and metadata", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.READ_WRITE });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("1. Explore and update object metadata", async ({ page }) => {
    await test.step("Go to the detailed page of any device", async () => {
      await page.goto("/objects/InfraDevice");
      await page.getByRole("link", { name: "atl1-core2" }).click();
    });

    await test.step("Explore Description attribute metadata", async () => {
      await page.getByText("Description-").getByTestId("view-metadata-button").click();
      await expect(page.getByText("Is protected: False")).toBeVisible();
      await saveScreenshotForDocs(page, "tutorial_4_metadata");
    });

    await test.step("Update Description attribute to make it protected", async () => {
      await page.getByTestId("edit-metadata-button").click();
      await page.getByTestId("select2step-1").first().getByRole("button").click();
      await page.getByRole("option", { name: "Account" }).click();
      await page.getByTestId("select2step-2").first().getByRole("button").click();
      await page.getByRole("option", { name: "Admin" }).click();
      await page.getByLabel("is protected *").check();
      await saveScreenshotForDocs(page, "tutorial_4_metadata_edit");
      await page.getByRole("button", { name: "Save" }).click();

      await page.getByText("Description-").getByTestId("view-metadata-button").click();

      await expect(page.getByText("Is protected: True")).toBeVisible();
    });

    await test.step("Not allowed to updated description because user is not admin", async () => {
      await page.getByRole("button", { name: "Edit" }).click();
      await expect(page.getByLabel("Description")).toBeDisabled();
    });
  });
});
