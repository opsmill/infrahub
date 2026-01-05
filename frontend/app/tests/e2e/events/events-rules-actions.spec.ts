import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, saveScreenshotForDocs } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("Event Rules and Actions", () => {
  test.describe.configure({ mode: "parallel" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("events-rules-actions");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test.fixme("1. Create and configure an Event with a Group Action", async ({ page }) => {
    await test.step("Create a Group action", async () => {
      // Navigate to the Actions page
      await page.goto(`/objects/CoreAction?branch=${BRANCH_NAME}`);
      // Configure Group action
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Group Action" }).click();
      await page.getByRole("textbox", { name: "Name *" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("add-to-group-arista_devices");
      await page.getByRole("combobox", { name: "Kind" }).click();
      await page.getByRole("option", { name: "Standard Group Core" }).click();
      await page.getByRole("combobox", { name: "Standard Group *" }).click();
      await page.getByPlaceholder("Filter...").fill("arista");
      await page.getByText("arista_devices").click();
      // Save screenshot Form
      await saveScreenshotForDocs(page, "guides/events/grp_actions-form-creation");
      await page.getByRole("button", { name: "Save" }).click();
      await page.getByRole("link", { name: "add-to-group-arista_devices" }).click();
      // Save screenshot Details
      await expect(page.getByText("Activities")).toBeVisible();
      await saveScreenshotForDocs(page, "guides/events/grp_actions-details");
    });

    // Trigger Tests
    await test.step("Create a Node trigger", async () => {
      // Navigate to the Triggers page
      await page.goto(`/objects/CoreTriggerRule?branch=${BRANCH_NAME}`);
      // Configure Node trigger
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Node Trigger" }).click();
      await page.getByRole("textbox", { name: "Name *" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("new-arista-devices");
      await page.getByRole("combobox", { name: "Node Kind *" }).click();
      await page.getByPlaceholder("Filter...").fill("device");
      await page.getByText("Device Infra").click();
      await page.getByRole("combobox", { name: "Mutation Action *" }).click();
      await page.getByRole("option", { name: "created" }).click();
      await page.getByRole("combobox", { name: "Kind", exact: true }).click();
      await page.getByRole("option", { name: "Group Action Core" }).click();
      await page.getByRole("combobox", { name: "Group Action *" }).click();
      await page.getByText("add-to-group-arista_devices").click();
      // Save screenshot Form
      await saveScreenshotForDocs(page, "guides/events/node-trigger-form-creation");
      await page.getByRole("button", { name: "Save" }).click();
      // Add Match to Node trigger
      await page.getByRole("link", { name: "new-arista-devices" }).click();
      await page.getByRole("link", { name: "Matches" }).click();
      await page.getByTestId("open-relationship-form-button").click();
      await page.getByRole("combobox", { name: "Select an object type" }).click();
      await page.getByText("Node Trigger Relationship").click();
      await page.getByRole("combobox", { name: "Relationship Name *" }).click();
      await page.getByText("Platform").click();
      await page.getByRole("combobox", { name: "Peer" }).click();
      await page.getByText("Arista EOS").click();
      // Save screenshot Match Form
      await saveScreenshotForDocs(page, "guides/events/node-trigger-matches-form-creation");
      await page.getByRole("button", { name: "Save" }).click();
    });
  });

  // FIXME: Understand why the generator is not found in the e2e tests during CICD.
  // test("2. Create and configure an Event with a Generator Action", async ({ page }) => {
  //   await test.step("Create a Generator action", async () => {
  //     // Navigate to the Actions page
  //     await page.goto(`/objects/CoreAction?branch=${BRANCH_NAME}`);
  //     // Configure Generator action
  //     await page.getByTestId("create-object-button").click();
  //     await page.getByLabel("Select an object type").click();
  //     await page.getByRole("option", { name: "Generator Action" }).click();
  //     await page.getByRole("textbox", { name: "Name *" }).click();
  //     await page.getByRole("textbox", { name: "Name *" }).click();
  //     await page.getByRole("textbox", { name: "Name *" }).fill("create_circuit_endpoints");
  //     await page.getByRole("combobox", { name: "Generator *" }).click();
  //     await page.getByText("create_circuit_endpoints").click();
  //     // Save screenshot Generator Form
  //     await saveScreenshotForDocs(page, "guides/events/generator-action-form-creation");
  //     await page.getByRole("button", { name: "Save" }).click();
  //   });
  //   await test.step("Create a Group trigger", async () => {
  //     // Navigate to the Triggers page
  //     await page.goto(`/objects/CoreTriggerRule?branch=${BRANCH_NAME}`);
  //     // Configure Group trigger
  //     await page.getByTestId("create-object-button").click();
  //     await page.getByLabel("Select an object type").click();
  //     await page.getByRole("option", { name: "Group Trigger" }).click();
  //     await page.getByRole("textbox", { name: "Name *" }).click();
  //     await page
  //       .getByRole("textbox", { name: "Name *" })
  //       .fill("added-to-provisioning-circuits-group");
  //     await page
  //       .getByTestId("side-panel-container")
  //       .locator("div")
  //       .filter({ hasText: "Group *?Kind ?" })
  //       .getByLabel("Kind")
  //       .click();
  //     await page.getByRole("option", { name: "Standard Group Core" }).click();
  //     await page.getByRole("combobox", { name: "Standard Group *" }).click();
  //     await page.getByText("provisioning_circuits").click();
  //     await page
  //       .getByTestId("side-panel-container")
  //       .locator("div")
  //       .filter({ hasText: "Action *?Kind ?" })
  //       .getByLabel("Kind")
  //       .click();
  //     await page.getByRole("option", { name: "Generator Action Core" }).click();
  //     await page.getByRole("combobox", { name: "Generator Action *" }).click();
  //     await page.getByText("create_circuit_endpoints").click();
  //     // Save screenshot Group Trigger Form
  //     await saveScreenshotForDocs(page, "guides/events/group-trigger-form-creation");
  //     await page.getByRole("button", { name: "Save" }).click();
  //   });
  // });
});
