import { expect, test } from "@playwright/test";

test.describe("/objects/CoreArtifact - Artifact page", () => {
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

          if (reqData?.operationName === "CoreArtifact" && status === 200) {
            json = response.json();
            return true;
          }
          return false;
        }),

        page.goto(
          // eslint-disable-next-line quotes
          '/objects/CoreArtifact?filters=[{"name":"name__value","value":"Startup Config for Edge devices"}]'
        ),
      ]);

      artifactCount = (await json)?.data?.CoreArtifact?.count;
    }
    await page.getByRole("link", { name: "startup Config for Edge devices" }).first().click();
    await expect(page.getByText("no aaa root").first()).toBeVisible();
  });
});
