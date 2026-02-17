import type { Page } from "@playwright/test";

/**
 * Helper to upload a file using Playwright's setInputFiles
 * Can accept either a file object from createTestFile() or raw options
 */
export async function uploadFile(
  page: Page,
  options:
    | {
        name: string;
        mimeType: string;
        buffer: Buffer;
      }
    | {
        name: string;
        mimeType: string;
        content: string;
      }
) {
  const fileInput = page.locator('input[type="file"]');

  // Check if it's already a buffer or needs conversion
  const buffer = "buffer" in options ? options.buffer : Buffer.from(options.content);

  await fileInput.setInputFiles({
    name: options.name,
    mimeType: options.mimeType,
    buffer,
  });
}

/**
 * Common file types for testing
 */
export const TEST_FILE_TYPES = {
  TEXT: { mimeType: "text/plain", extension: ".txt" },
  JSON: { mimeType: "application/json", extension: ".json" },
  YAML: { mimeType: "application/x-yaml", extension: ".yaml" },
  CSV: { mimeType: "text/csv", extension: ".csv" },
  PDF: { mimeType: "application/pdf", extension: ".pdf" },
  PNG: { mimeType: "image/png", extension: ".png" },
  JPEG: { mimeType: "image/jpeg", extension: ".jpg" },
} as const;

/**
 * Generate a test file with random content
 */
export function generateTestFileContent(size: "small" | "medium" | "large" = "small"): string {
  const sizes = {
    small: 100, // ~100 bytes
    medium: 1024, // ~1KB
    large: 10_240, // ~10KB
  };

  const targetSize = sizes[size];
  const line = "This is a test line of content.\n";
  const repeatCount = Math.ceil(targetSize / line.length);

  return line.repeat(repeatCount);
}

/**
 * Create a test file buffer from template
 */
export function createTestFile(
  fileName: string,
  fileType: keyof typeof TEST_FILE_TYPES = "TEXT",
  content?: string
): { name: string; mimeType: string; buffer: Buffer } {
  const type = TEST_FILE_TYPES[fileType];
  const defaultContent = content || generateTestFileContent("small");

  return {
    name: fileName,
    mimeType: type.mimeType,
    buffer: Buffer.from(defaultContent),
  };
}

/**
 * Fill required fields for InfraCircuitContract
 */
export async function fillCircuitContractFields(
  page: Page,
  options?: {
    contractNumber?: string;
    vendor?: string;
    startDate?: string;
    endDate?: string;
  }
) {
  const defaults = {
    contractNumber: `CONTRACT-${Date.now()}`,
    vendor: "Test Vendor Inc",
    startDate: "2024-01-01",
    endDate: "2025-12-31",
    ...options,
  };

  // Wait for form to be ready
  await page.getByLabel("Contract Number").first().waitFor({ state: "visible" });

  await page.getByLabel("Contract Number").first().fill(defaults.contractNumber);
  await page.getByLabel("Vendor").first().fill(defaults.vendor);
  await page.getByLabel("Start Date").first().fill(defaults.startDate);
  await page.getByLabel("End Date").first().fill(defaults.endDate);
}
