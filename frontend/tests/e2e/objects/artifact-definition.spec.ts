import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/objects/CoreArtifactDefinition - Artifact Definition page", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should generate artifacts successfully", async ({ page }) => {
    await page.goto("/objects/CoreArtifactDefinition");
    await page.getByRole("link", { name: "startup-config" }).click();
    await page.getByRole("button", { name: "Generate" }).click();
    await expect(page.getByRole("alert")).toContainText("Artifacts generated");
  });
});
