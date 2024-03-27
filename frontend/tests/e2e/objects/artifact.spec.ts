import { expect, test } from "@playwright/test";

test.describe("/objects/CoreArtifact - Artifact page", () => {
  test("should generate artifacts successfully", async ({ page }) => {
    await page.goto("/objects/CoreArtifact");
    await page.getByRole("link", { name: "startup Config for Edge devices" }).first().click();
    await expect(page.getByText("no aaa root").first()).toBeVisible();
  });
});
