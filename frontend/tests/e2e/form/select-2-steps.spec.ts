import { test, expect } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

const ETHERNET_NAME = "New ethernet name";
const ETHERNET_SPEED = "1000";
const DEVICE_NAME = "atl1-core1";
const KIND = "InterfaceL3";
const ENDPOINT_NAME = "et-0/0/2";

test.describe("Verifies the object creation", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("creates and verifies the objects values", async ({ page }) => {
    await test.step("creates the object", async () => {
      // FIXME: fix showing dropdown when InfraInterfaceL3 takes some time
      await Promise.all([
        page.waitForResponse((response) => {
          const reqData = response.request().postDataJSON();
          const status = response.status();

          return reqData?.operationName === "InfraInterfaceL3" && status === 200;
        }),
        page.goto("/objects/InfraInterfaceL3"),
      ]);
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Name *").fill(ETHERNET_NAME);
      await page.getByLabel("Speed *").fill(ETHERNET_SPEED);
      await page
        .locator("div:below(:text('Device *'))")
        .first()
        .getByTestId("select-open-option-button")
        .click();
      await page.getByText(DEVICE_NAME).click();
      await page.getByTestId("select2step-1").getByTestId("select-open-option-button").click();
      await page.getByRole("option", { name: KIND }).click();
      await page.getByTestId("select2step-2").getByTestId("select-open-option-button").click();
      await page.getByRole("option", { name: ENDPOINT_NAME }).last().click();
      await page.getByRole("button", { name: "Create" }).click();
      await expect(page.getByText(`${KIND} created`)).toBeVisible();
    });

    await test.step("verifies the object values", async () => {
      await page.getByPlaceholder("Search anywhere").click();
      await page
        .getByTestId("search-anywhere")
        .getByPlaceholder("Search anywhere")
        .fill(ETHERNET_NAME);
      await page.getByRole("option", { name: `${ETHERNET_NAME}Interface L3` }).click();
      await expect(page.getByRole("main")).toContainText(ETHERNET_NAME);
      await expect(page.getByRole("main")).toContainText(ETHERNET_SPEED);
      await expect(page.getByRole("main")).toContainText(ENDPOINT_NAME);
      await expect(page.getByRole("main")).toContainText(DEVICE_NAME);
    });

    await test.step("verifies the form values", async () => {
      await page.getByRole("button", { name: "Edit" }).click();
      await expect(page.getByLabel("Speed *")).toHaveValue(ETHERNET_SPEED);
      await expect(
        page.locator("div:below(:text('Device *'))").getByTestId("select-input").first()
      ).toHaveValue(DEVICE_NAME);
      await expect(page.getByTestId("select2step-1").getByTestId("select-input")).toHaveValue(KIND);
      await expect(page.getByTestId("select2step-2").getByTestId("select-input")).toHaveValue(
        ENDPOINT_NAME
      );
    });
  });
});
