import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/objects/CoreArtifactDefinition - Artifact Definition page", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should generate artifacts successfully", async ({ page }) => {
    await page.goto("/objects/CoreArtifactDefinition");
    await page.getByRole("link", { name: "startup-config" }).click();
    await page.getByRole("button", { name: "Generate" }).click();
    await expect(page.getByRole("alert")).toContainText("Artifacts generated");
  });
});
