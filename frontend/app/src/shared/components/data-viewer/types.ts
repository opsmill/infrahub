const TEXT_CONTENT_TYPES = [
  "application/json",
  "application/yaml",
  "application/hcl",
  "application/graphql",
  "image/svg+xml",
  "text/plain",
  "text/markdown",
  "application/xml",
  "text/csv",
] as const;

const IMAGE_CONTENT_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"] as const;

export type TextContentType = (typeof TEXT_CONTENT_TYPES)[number];
export type ImageContentType = (typeof IMAGE_CONTENT_TYPES)[number];
export type PdfContentType = "application/pdf";
export type ContentType = TextContentType | ImageContentType | PdfContentType;

/**
 * Viewer type determined from content type.
 * Used internally to decide which rendering strategy to use.
 */
export type ViewerType =
  | { type: "text"; textContentType: TextContentType }
  | { type: "image"; imageContentType: ImageContentType }
  | { type: "pdf" }
  | { type: "unsupported" };

export function getViewerType(contentType?: string): ViewerType {
  if (!contentType) {
    return { type: "unsupported" };
  }

  if (TEXT_CONTENT_TYPES.includes(contentType as TextContentType)) {
    return { type: "text", textContentType: contentType as TextContentType };
  }

  // Common YAML variation
  if (contentType === "application/x-yaml") {
    return { type: "text", textContentType: "application/yaml" };
  }

  // Other text/* types fallback to plain text
  if (contentType.startsWith("text/")) {
    return { type: "text", textContentType: "text/plain" };
  }

  // Images (except SVG which is handled above as text)
  if (IMAGE_CONTENT_TYPES.includes(contentType as ImageContentType)) {
    return { type: "image", imageContentType: contentType as ImageContentType };
  }

  // PDF
  if (contentType === "application/pdf") {
    return { type: "pdf" };
  }

  return { type: "unsupported" };
}
