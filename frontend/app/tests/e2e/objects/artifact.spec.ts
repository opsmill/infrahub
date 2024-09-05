import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/objects/CoreArtifact - Artifact page", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should generate artifacts successfully", async ({ page }) => {
    await page.goto(
      '/objects/CoreArtifact?filters=[{"name":"name__value","value":"Startup Config for Edge devices"}]'
    );

    // reload page until we have artifacts defined
    while (
      await page.getByRole("link", { name: "startup Config for Edge devices" }).first().isHidden()
    ) {
      await page.reload();
      await expect(page.getByText("Previous")).toBeVisible();
    }

    await page.getByRole("link", { name: "startup Config for Edge devices" }).first().click();
    await expect(page.getByText("no aaa root").first()).toBeVisible();
  });

  test.describe("when logged in", async () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should not be able to create a new artifact", async ({ page }) => {
      await page.goto("/objects/CoreArtifact");
      await expect(page.getByRole("heading", { name: "Artifact" })).toBeVisible();
      await expect(page.getByTestId("create-object-button")).not.toBeVisible();
    });

    test("should add generated artifact to a group", async ({ page }) => {
      await page.goto(
        // eslint-disable-next-line quotes
        '/objects/CoreArtifact?filters=[{"name":"name__value","value":"Startup Config for Edge devices"}]'
      );
      await page.getByRole("link", { name: "startup Config for Edge devices" }).first().click();

      await test.step("add artifact to a group", async () => {
        await page.getByRole("button", { name: "Manage groups" }).click();
        await page.getByTestId("open-group-form-button").click();

        await page.getByTestId("select-open-option-button").click();
        await page.getByRole("option", { name: "arista_devices" }).click();
        await page.getByTestId("select-open-option-button").click();
        await page.getByRole("button", { name: "Save" }).click();

        await expect(page.getByText("1 group added")).toBeVisible();
      });

      await test.step("remove artifact from a group", async () => {
        await page.getByTestId("leave-group-button").first().click();
        await page.getByTestId("modal-delete-confirm").click();

        await expect(page.getByRole("link", { name: "arista_devices" })).not.toBeVisible();
      });
    });
  });
});
