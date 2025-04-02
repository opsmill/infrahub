import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

const ETHERNET_NAME = "New ethernet name";
const ETHERNET_SPEED = "1000";
const DEVICE_NAME = "atl1-core1";
const KIND = "InterfaceL3";
const ENDPOINT_NAME = "et-0/0/2";

test.describe("Verifies the object creation", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.describe.configure({ mode: "serial" });

  const BRANCH_NAME = generateRandomBranchName();

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("creates and verifies the nodes values", async ({ page }) => {
    await test.step("creates the object", async () => {
      await page.goto(`/objects/InfraInterfaceL3?branch=${BRANCH_NAME}`);
      await expect(page.getByText("Loading...")).toBeHidden();
      await expect(page.getByText("Skeleton placeholder")).toBeHidden();
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Name *").fill(ETHERNET_NAME);
      await page.getByLabel("Speed *").fill(ETHERNET_SPEED);
      await page.getByRole("combobox", { name: "Device", exact: true }).click();
      await page.getByText(DEVICE_NAME).click();
      await page.getByRole("combobox", { name: "Lag", exact: true }).click();

      // Wait for query to load options
      await expect(page.getByText("Loading...")).toBeHidden();

      await page.getByRole("option", { name: ENDPOINT_NAME }).last().click();
      await page.getByRole("button", { name: "Save" }).click();
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
      await page.getByTestId("edit-button").click();
      await expect(page.getByLabel("Speed *")).toHaveValue(ETHERNET_SPEED);
      await page.getByRole("combobox", { name: "Device", exact: true }).click();

      await expect(
        page.getByRole("combobox", { name: "Device", exact: true }).getByTestId("select-value")
      ).toHaveValue(DEVICE_NAME);
      await expect(
        page.getByRole("combobox", { name: "Lag", exact: true }).getByTestId("select-value")
      ).toHaveValue(ENDPOINT_NAME);
    });
  });

  test("verifies empty values after kind select", async ({ page }) => {
    await page.goto(`/objects/CoreGraphQLQuery?branch=${BRANCH_NAME}`);
    await page.getByTestId("create-object-button").click();
    await page.getByLabel("Kind").click();
    await page.getByRole("option", { name: "Repository Core", exact: true }).click();
    await page.getByLabel("Repository").click();
    await expect(page.getByText("Read-Only Repository", { exact: true })).not.toBeVisible();
  });

  test("verifies values in kind and parent selects", async ({ page }) => {
    await test.step("got to the edit form", async () => {
      await page.goto(`/objects/InfraInterfaceL3?branch=${BRANCH_NAME}`);
      await page
        .getByTestId("identifier-cell")
        .getByRole("link", { name: "dfw1-edge1, Ethernet1", exact: true })
        .click();
      await page.getByTestId("edit-button").click();
    });

    await test.step("check inputs values", async () => {
      await expect(page.getByLabel("Kind")).toContainText("Interface L3 Infra");
      await expect(page.locator('button[name="connected_endpoint_parent"]')).toContainText(
        "dfw1-edge2"
      );
      await expect(
        page.getByTestId("side-panel-container").getByLabel("Interface L3")
      ).toContainText("Ethernet1");

      await page.getByTestId("side-panel-container").getByLabel("Interface L3").click();
      await expect(page.getByRole("option", { name: "Ethernet10" })).toBeVisible();
      await expect(page.getByRole("option", { name: "Loopback0" })).toBeVisible();
      await expect(page.getByRole("option", { name: "Management0" })).toBeVisible();
    });
  });
});
