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
    let artifactCount = 0;
    while (artifactCount == 0) {
      // reload page until we have artifacts defined
      let json: any;
      await Promise.all([
        page.waitForResponse((response) => {
          const reqData = response.request().postDataJSON();
          const status = response.status();

          if (reqData?.operationName === "CoreArtifactDefinition" && status === 200) {
            json = response.json();
            return true;
          }
          return false;
        }),

        page.goto("/objects/CoreArtifactDefinition"),
      ]);

      artifactCount = (await json)?.data?.CoreArtifactDefinition?.count;
    }
    await page.getByRole("link", { name: "startup-config" }).click();
    await page.getByRole("button", { name: "Generate" }).click();
    await expect(page.getByRole("alert")).toContainText("Artifacts generated");
  });
});
