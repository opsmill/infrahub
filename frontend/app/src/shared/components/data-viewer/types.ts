/**
 * Text MIME content types for DataViewer component.
 * Used to determine how content is rendered (code viewer, markdown, SVG, etc.)
 */
export type TextContentType =
  | "application/json"
  | "application/yaml"
  | "application/hcl"
  | "application/graphql"
  | "image/svg+xml"
  | "text/plain"
  | "text/markdown"
  | "application/xml"
  | "text/csv";

/** @deprecated Use TextContentType instead */
export type DataViewerContentType = TextContentType;

/**
 * Viewer type determined from content type.
 * - text: Renderable text content (code, markdown, csv, svg)
 * - image: Binary image content (png, jpeg, gif, etc.)
 * - pdf: PDF document
 * - unsupported: Content type not supported for preview
 */
export type ViewerType =
  | { type: "text"; textContentType: TextContentType }
  | { type: "image"; imageContentType: string }
  | { type: "pdf" }
  | { type: "unsupported" };

const TEXT_CONTENT_TYPES: TextContentType[] = [
  "application/json",
  "application/yaml",
  "application/hcl",
  "application/graphql",
  "image/svg+xml",
  "text/plain",
  "text/markdown",
  "application/xml",
  "text/csv",
];

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
  if (contentType.startsWith("image/")) {
    return { type: "image", imageContentType: contentType };
  }

  // PDF
  if (contentType === "application/pdf") {
    return { type: "pdf" };
  }

  return { type: "unsupported" };
}
