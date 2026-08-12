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
 * Build a valid, minimal single-page PDF document.
 *
 * The browser's PDF viewer (PDFium) validates the document structure when a
 * saved file is previewed in an `<iframe src="data:application/pdf;...">`.
 * Uploading plain text with a `application/pdf` mime type makes the viewer fail
 * with "Failed to load PDF document", so PDF tests must use real PDF bytes.
 */
export function createMinimalPdfBuffer(text = "Mock PDF content for E2E testing"): Buffer {
  const escaped = text.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
  const stream = `BT /F1 18 Tf 36 100 Td (${escaped}) Tj ET`;

  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents 4 0 R >>",
    `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`,
  ];

  let body = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((object, index) => {
    offsets.push(Buffer.byteLength(body));
    body += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });

  const xrefOffset = Buffer.byteLength(body);
  let xref = `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) {
    xref += `${String(offset).padStart(10, "0")} 00000 n \n`;
  }
  const trailer = `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`;

  return Buffer.from(body + xref + trailer);
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
  const defaultContent = content ?? generateTestFileContent("small");

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

  const form = page.getByLabel("sheet");

  // Wait for form to be ready
  await form.getByLabel("Contract Number").waitFor({ state: "visible" });

  await form.getByLabel("Contract Number").fill(defaults.contractNumber);
  await form.getByLabel("Vendor").fill(defaults.vendor);
  await form.getByLabel("Start Date").fill(defaults.startDate);
  await form.getByLabel("End Date").fill(defaults.endDate);
}
