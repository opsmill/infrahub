import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/objects/CoreArtifactDefinition - Artifact Definition page", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should generate artifacts successfully", async ({ page }) => {
    await page.goto("/objects/CoreArtifactDefinition");
    const breadcrumb = page.getByTestId("breadcrumb-navigation");
    await expect(breadcrumb.getByRole("link", { name: "Artifact Definition" })).toBeVisible();

    await page.getByRole("link", { name: "Startup Config for Edge devices" }).click();
    await expect(breadcrumb.getByRole("link", { name: "Artifact Definition" })).toBeVisible();
    await expect(
      breadcrumb.getByRole("link", { name: "Startup Config for Edge devices" })
    ).toBeVisible();

    await expect(page.getByRole("button", { name: "Generate" })).not.toBeDisabled();
    await page.getByRole("button", { name: "Generate" }).click();
    await expect(page.getByText("Artifacts generated")).toBeVisible();
  });
});
