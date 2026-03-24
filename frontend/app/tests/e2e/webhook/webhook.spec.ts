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
