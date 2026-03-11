import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("/objects/CoreWebhook", () => {
  test.describe("when logged in as admin account", () => {
    test.describe.configure({ mode: "serial" });
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("Create a webhook", async ({ page }) => {
      await test.step("load webhooks", async () => {
        await page.goto("/objects/CoreWebhook");
        await expect(page.getByTestId("object-header")).toContainText("Webhook");
        await saveScreenshotForDocs(page, "webhook_list");
      });

      await test.step("create a new webhook", async () => {
        await page.getByTestId("create-object-button").click();

        await page.getByLabel("Select an object type").click();
        await page.getByRole("option", { name: "Standard Webhook Core" }).click();

        await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
        await page.getByLabel("Name *").fill("Ansible EDA");

        await page.getByLabel("Branch Scope").click();
        await page.getByRole("option", { name: "All Branches All branches" }).click();

        await page.getByRole("combobox", { name: "Node Kind" }).click();
        await page.getByRole("option", { name: "Account Core" }).click();

        await page.getByLabel("Description").fill("Ansible EDA Webhook Reciever");

        await page.getByLabel("Url *").fill("http://ansible-eda:8080");

        await page.getByLabel("Shared Key *").fill("secret");

        await page.getByLabel("Validate Certificates").uncheck();

        await saveScreenshotForDocs(page, "webhook_create");

        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByText("Webhook created")).toBeVisible();
      });
    });

    test("Access webhook", async ({ page }) => {
      await test.step("load webhooks", async () => {
        await page.goto("/objects/CoreWebhook");
        await expect(page.getByTestId("object-header")).toContainText("Webhook");
      });

      await test.step("webhook detail view", async () => {
        // Give time for activity log to be propagated.
        await page
          .getByTestId("identifier-cell")
          .getByRole("link", { name: "Ansible EDA", exact: true })
          .click();

        await expect(page.getByText("Activities", { exact: true })).toBeVisible();
        await expect(page.getByTestId("activities-panel").getByText("Loading...")).toBeHidden();

        while (await page.getByText("No activity found for this").isVisible()) {
          await page.reload();
          await expect(page.getByText("Activities", { exact: true })).toBeVisible();
          await expect(page.getByTestId("activities-panel").getByText("Loading...")).toBeHidden();
        }
        await expect(page.getByText("NameAnsible EDA")).toBeVisible();
        await expect(page.getByText("View all activities")).toBeVisible();
        await saveScreenshotForDocs(page, "webhook_detail");
      });
    });

    test("Create a key-value header and associate it with the webhook", async ({ page }) => {
      await test.step("create a password key-value pair", async () => {
        await page.goto("/objects/CoreKeyValue");
        await expect(page.getByTestId("object-header")).toContainText("Key Value");
        await page.getByTestId("create-object-button").click();

        await page.getByLabel("Select an object type").click();
        await page.getByRole("option", { name: "Password Key Value" }).click();

        await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
        await page.getByLabel("Name *").fill("eda-auth-token");
        await page.getByLabel("Key *").fill("Authorization");
        await page.getByLabel("Value *").fill("Bearer e2e-test-token");

        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByRole("link", { name: "eda-auth-token" })).toBeVisible();
      });

      await test.step("associate header with webhook", async () => {
        await page.goto("/objects/CoreWebhook");
        await expect(page.getByTestId("object-header")).toContainText("Webhook");
        await page
          .getByTestId("identifier-cell")
          .getByRole("link", { name: "Ansible EDA", exact: true })
          .click();

        await expect(
          page.getByTestId("object-header").getByText("Ansible EDA", { exact: true })
        ).toBeVisible();

        // Navigate to the Headers relationship tab
        await page.getByRole("link", { name: "Headers 0" }).click();
        await expect(page.getByText("No Key Value found")).toBeVisible();

        // Add the header via the relationship form
        await page.getByTestId("open-relationship-form-button").click();
        await page.getByRole("combobox", { name: "Kind" }).click();
        await page.getByRole("option", { name: "Password Key Value" }).click();
        await page.getByRole("combobox").last().click();
        await page.getByRole("option", { name: "eda-auth-token" }).click();
        await page.getByRole("button", { name: "Save" }).click();

        // Verify the header appears in the relationship list
        await expect(page.getByRole("link", { name: "eda-auth-token" })).toBeVisible();
      });
    });

    test("Delete webhook", async ({ page }) => {
      await test.step("load webhooks", async () => {
        await page.goto("/objects/CoreWebhook");
        await expect(page.getByTestId("object-header")).toContainText("Webhook");
      });

      await test.step("access and delete webhook", async () => {
        await page.getByRole("link", { name: "Ansible EDA" }).click();
        await expect(
          page.getByTestId("object-header").getByText("Ansible EDA", { exact: true })
        ).toBeVisible();
        await page.getByTestId("object-details-menu").click();
        await page.getByRole("menuitem", { name: "Delete" }).click();
        await page.getByTestId("modal-delete-confirm").click();
        await expect(page.getByText("Object Ansible EDA deleted")).toBeVisible();
        await page.getByText("No Standard Webhook found").click();
      });
    });
  });
});
