import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe.fixme("/objects/CoreArtifact - Artifact page", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.slow();

  test("should generate artifacts successfully", async ({ page }) => {
    await page.goto(
      '/objects/CoreArtifact?filters=[{"name":"name__value","value":"startup-config"}]'
    );

    // reload page until we have artifacts defined
    while (await page.getByRole("link", { name: "startup-config" }).first().isHidden()) {
      if (await page.getByText("No Artifact found").isVisible()) {
        await page.reload();
      }
    }

    await page.getByRole("link", { name: "startup-config" }).first().click();
    await expect(page.getByText("no aaa root").first()).toBeVisible();
  });

  test.describe("when logged in", async () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should not be able to create a new artifact", async ({ page }) => {
      await page.goto("/objects/CoreArtifact");
      await expect(page.getByRole("heading", { name: "Artifact" })).toBeVisible();
      await expect(page.getByTestId("create-object-button")).not.toBeVisible();
    });
  });
});
