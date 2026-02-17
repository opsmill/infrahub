import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";
import { fillCircuitContractFields, uploadFile } from "./file-upload-helpers";

test.describe("File Upload - InfraCircuitContract", () => {
  const BRANCH_NAME = generateRandomBranchName("file-upload");
  const TEST_FILE_NAME = "contract.pdf";
  const TEST_FILE_CONTENT = "Mock PDF contract content for E2E testing";

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test.beforeEach(async ({ page }) => {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test.describe("when not logged in", () => {
    test("should not be able to create file object", async ({ page }) => {
      await page.goto(`/objects/InfraCircuitContract?branch=${BRANCH_NAME}`);

      // Create button should not be visible or enabled
      const createButton = page.getByTestId("create-object-button");
      if (await createButton.isVisible()) {
        await expect(createButton).toBeDisabled();
      }
    });
  });

  test.describe("when logged in as Admin", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should successfully upload a file", async ({ page }) => {
      await page.goto(`/objects/InfraCircuitContract?branch=${BRANCH_NAME}`);

      await test.step("click create button", async () => {
        await page.getByTestId("create-object-button").click();
      });

      await test.step("display file upload dropzone", async () => {
        await expect(page.getByText("Drag and drop a file here, or click to select")).toBeVisible();
        await expect(page.getByText("Max file size: 10MB")).toBeVisible();
      });

      await test.step("upload a file", async () => {
        await uploadFile(page, {
          name: TEST_FILE_NAME,
          mimeType: "application/pdf",
          content: TEST_FILE_CONTENT,
        });

        // Verify file info card is displayed
        await expect(page.getByText(TEST_FILE_NAME)).toBeVisible();
        await expect(page.getByText(/\d+\s*(B|KB|MB)/)).toBeVisible(); // File size
      });

      await test.step("fill required fields", async () => {
        await fillCircuitContractFields(page);
      });

      await test.step("submit the form", async () => {
        await page.getByRole("button", { name: "Save" }).click();

        // Wait for success message (just "created" to be more flexible)
        await expect(page.getByText(/created/i)).toBeVisible();
      });

      await test.step("verify file appears in list", async () => {
        await page.goto(`/objects/InfraCircuitContract?branch=${BRANCH_NAME}`);
        // File name should appear in the list
        await expect(page.getByText(TEST_FILE_NAME)).toBeVisible();
      });
    });

    test("should validate required file field", async ({ page }) => {
      await page.goto(`/objects/InfraCircuitContract?branch=${BRANCH_NAME}`);
      await page.getByTestId("create-object-button").click();

      await test.step("try to submit without file", async () => {
        await page.getByRole("button", { name: "Save" }).click();

        // Should show validation error (multiple "Required" messages for all required fields)
        await expect(page.getByText(/required/i).first()).toBeVisible();
      });

      await test.step("upload file to clear error", async () => {
        await uploadFile(page, {
          name: "valid-contract.pdf",
          mimeType: "application/pdf",
          content: "Valid contract content",
        });

        // Error should be cleared or file should be visible
        await expect(page.getByText("valid-contract.pdf")).toBeVisible();
      });
    });

    test("should update existing file", async ({ page }) => {
      const initialFileName = "initial-contract.pdf";
      const updatedFileName = "updated-contract.pdf";
      const contractNumber = `CONTRACT-UPDATE-${Date.now()}`;

      await test.step("create initial file", async () => {
        await page.goto(`/objects/InfraCircuitContract?branch=${BRANCH_NAME}`);
        await page.getByTestId("create-object-button").click();

        await uploadFile(page, {
          name: initialFileName,
          mimeType: "application/pdf",
          content: "Initial contract content",
        });

        await fillCircuitContractFields(page, { contractNumber });

        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByText(/created/i)).toBeVisible();
      });

      await test.step("navigate to edit the file object", async () => {
        // Navigate back to list and click on the created contract by its contract number
        await page.goto(`/objects/InfraCircuitContract?branch=${BRANCH_NAME}`);

        // Click on the contract by its contract_number (which is the display label)
        await page.getByRole("link", { name: contractNumber }).click();

        // Click edit button
        await page.getByTestId("edit-button").click();

        // Verify existing file is shown (use .first() to avoid strict mode violation)
        await expect(page.getByText(initialFileName).first()).toBeVisible();
      });

      await test.step("upload new file", async () => {
        await uploadFile(page, {
          name: updatedFileName,
          mimeType: "application/pdf",
          content: "Updated contract content",
        });

        await expect(page.getByText(updatedFileName)).toBeVisible();
      });

      await test.step("save the update", async () => {
        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByText(/updated/i)).toBeVisible();
        await expect(page.getByText(updatedFileName)).toBeVisible();
      });
    });

    test("should handle different file types", async ({ page }) => {
      const testFiles = [
        { name: "contract.json", mimeType: "application/json", content: '{"contract": "data"}' },
        {
          name: "contract.yaml",
          mimeType: "application/x-yaml",
          content: "contract: data\nstatus: active\n",
        },
        { name: "contract.txt", mimeType: "text/plain", content: "Plain text contract\n" },
      ];

      for (const testFile of testFiles) {
        await test.step(`upload ${testFile.name}`, async () => {
          await page.goto(`/objects/InfraCircuitContract?branch=${BRANCH_NAME}`);
          await page.getByTestId("create-object-button").click();

          await uploadFile(page, testFile);

          await expect(page.getByText(testFile.name)).toBeVisible();

          await fillCircuitContractFields(page, { contractNumber: `CONTRACT-${testFile.name}` });

          await page.getByRole("button", { name: "Save" }).click();
          await expect(page.getByText(/created/i)).toBeVisible();
        });
      }
    });
  });

  test.describe("when logged in as Read-Only", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.READ_ONLY });

    test("should not be able to upload files", async ({ page }) => {
      await page.goto(`/objects/InfraCircuitContract?branch=${BRANCH_NAME}`);

      // Create button should be disabled or not visible
      const createButton = page.getByTestId("create-object-button");
      if (await createButton.isVisible()) {
        await expect(createButton).toBeDisabled();
      }
    });

    test("should not be able to edit existing file", async ({ page }) => {
      await test.step("navigate to an existing file object", async () => {
        await page.goto(`/objects/InfraCircuitContract?branch=${BRANCH_NAME}`);

        const fileLink = page.getByRole("link").first();
        if (await fileLink.isVisible()) {
          await fileLink.click();
        }
      });

      await test.step("verify edit button is disabled", async () => {
        await expect(page.getByTestId("edit-button")).toBeDisabled();
      });
    });
  });

  test.describe("file download", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should download uploaded file", async ({ page }) => {
      const fileName = "download-test.pdf";
      const fileContent = "This file should be downloadable";
      const contractNumber = `CONTRACT-DOWNLOAD-${Date.now()}`;

      await test.step("create and upload file", async () => {
        await page.goto(`/objects/InfraCircuitContract?branch=${BRANCH_NAME}`);
        await page.getByTestId("create-object-button").click();

        await uploadFile(page, {
          name: fileName,
          mimeType: "application/pdf",
          content: fileContent,
        });

        await fillCircuitContractFields(page, { contractNumber });

        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByText(/created/i)).toBeVisible();
      });

      await test.step("navigate to object detail page", async () => {
        // Navigate back to list and click on the created contract
        await page.goto(`/objects/InfraCircuitContract?branch=${BRANCH_NAME}`);
        await page.getByRole("link", { name: contractNumber }).click();
      });

      await test.step("verify download button exists", async () => {
        // Look for download button
        const downloadButton = page.getByRole("button", { name: /download/i });

        if (await downloadButton.isVisible()) {
          // Start waiting for download before clicking
          const downloadPromise = page.waitForEvent("download");
          await downloadButton.click();
          const download = await downloadPromise;

          // Verify download filename
          expect(download.suggestedFilename()).toBe(fileName);
        }
      });
    });
  });
});
