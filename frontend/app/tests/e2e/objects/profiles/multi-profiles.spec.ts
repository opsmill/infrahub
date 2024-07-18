import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../../constants";

test.describe("/objects/CoreProfile - Profiles page", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should create 3 new profiles for the interfaces and use them in the form", async ({
    page,
  }) => {
    await test.step("creates profiles", async () => {
      await page.goto("/objects/CoreProfile");

      // Generic profile
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "ProfileInfraInterface Profile" }).click();
      await page.getByLabel("Profile Name *").fill("Generic profile");
      await page.getByLabel("Description").fill("Desc from generic profile");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("InfraInterface created")).toBeVisible();
      await page.getByTestId("close-alert").click();
      await expect(page.getByText("InfraInterface created")).not.toBeVisible();

      // L2 profile v1
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "ProfileInfraInterfaceL2 Profile" }).click();
      await page.getByLabel("Profile Name *").fill("L2 profile v1");
      await page.getByLabel("Description").fill("Desc from L2 profile v1");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("InfraInterfaceL2 created")).toBeVisible();
      await page.getByTestId("close-alert").click();
      await expect(page.getByText("InfraInterfaceL2 created")).not.toBeVisible();

      // L2 profile v2
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "ProfileInfraInterfaceL2 Profile" }).click();
      await page.getByLabel("Profile Name *").fill("L2 profile v2");
      await page.getByLabel("Description").fill("Desc from L2 profile v2");
      await page.getByLabel("Profile Priority").fill("10");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("InfraInterfaceL2 created")).toBeVisible();
    });

    await test.step("use profiles in interface form", async () => {
      await page.goto("/objects/InfraInterface");
      await page.getByTestId("create-object-button").click();

      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Interface L2 Infra", exact: true }).click();

      await page.getByLabel("Select profiles optional").click();
      await page.getByRole("option", { name: "L2 profile v1" }).click();
      await expect(page.getByLabel("Description")).toHaveValue("Desc from L2 profile v1");

      await page.getByRole("option", { name: "L2 profile v2" }).click();
      await expect(page.getByLabel("Description")).toHaveValue("Desc from L2 profile v2");

      await page.getByRole("option", { name: "Generic profile" }).click();
      await expect(page.getByLabel("Description")).toHaveValue("Desc from L2 profile v2");

      await page.getByRole("option", { name: "L2 profile v2" }).click();
      await expect(page.getByLabel("Description")).toHaveValue("Desc from L2 profile v1");
    });
  });
});
