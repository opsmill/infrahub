import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe.fixme("object-template", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.describe.fixme("object-template diff data", () => {
    test.describe.configure({ mode: "serial" });
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
    test.slow();

    test.beforeEach(async function ({ page }) {
      page.on("response", async (response) => {
        if (response.status() === 500) {
          await expect(response.url()).toBe("This URL responded with a 500 status");
        }
      });
    });
  });

  test("create-object-instance-using-template", async ({ page }) => {
    await test.step("view-existing-template", async () => {
      await page.goto("/objects/CoreObjectTemplate");
      await expect(page.getByTestId("create-object-button")).toBeVisible();
      await saveScreenshotForDocs(page, "/guides/object-template/template_list");
    });

    await test.step("create-patch-panel-using-template", async () => {
      await page.goto("/objects/InfraPatchPanel");
      await expect(page.getByTestId("create-object-button")).toBeVisible();
      await page.getByTestId("create-object-button").click();
      await expect(page.getByRole("button", { name: "Start from template Pick a" })).toBeVisible();
      await saveScreenshotForDocs(page, "/guides/object-template/template_or_from_scratch");
      await page.getByRole("button", { name: "Start from template Pick a" }).click();
      await page.getByRole("option", { name: "Regular_Patch_Panel" }).click();
      await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
      await page.getByLabel("Name *").fill("patch-panel-01");
      await saveScreenshotForDocs(page, "/guides/object-template/form_with_template");
      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("view-created-object", async () => {
      await page.goto("/objects/InfraPatchPanel");
      await expect(page.getByText("Patch Panel used to connect racks")).toBeVisible();
      await page.getByTestId("identifier-cell").first().click();
      await expect(page.getByText("Front Interfaces6")).toBeVisible();
      await page.getByText("Front Interfaces6").click();
      await expect(page.getByText("patch-panel-01, C1.P01")).toBeVisible();
      await saveScreenshotForDocs(
        page,
        "/guides/object-template/object_components_created_using_template"
      );
    });
  });
});
