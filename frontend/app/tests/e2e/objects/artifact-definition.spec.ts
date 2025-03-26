import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe.fixme("/objects/CoreArtifactDefinition - Artifact Definition page", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.slow();

  test("should generate artifacts successfully", async ({ page }) => {
    await page.goto("/objects/CoreArtifactDefinition");
    await page.getByRole("link", { name: "Startup Config for Edge devices" }).click();
    await expect(page.getByRole("button", { name: "Generate" })).not.toBeDisabled();
    await page.getByRole("button", { name: "Generate" }).click();
    await expect(page.getByText("Artifacts generated")).toBeVisible();
  });
});
