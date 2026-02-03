/**
 * Supported MIME content types for DataViewer component.
 * Used to determine how content is rendered (code viewer, markdown, SVG, etc.)
 */
export type DataViewerContentType =
  | "application/json"
  | "application/yaml"
  | "application/hcl"
  | "application/graphql"
  | "image/svg+xml"
  | "text/plain"
  | "text/markdown"
  | "application/xml"
  | "text/csv";

/**
 * Viewer type determined from content type.
 * - text: Renderable text content (code, markdown, csv, svg)
 * - image: Binary image content (png, jpeg, gif, etc.)
 * - pdf: PDF document
 * - unsupported: Content type not supported for preview
 */
export type ViewerType =
  | { type: "text"; dataViewerContentType: DataViewerContentType }
  | { type: "image" }
  | { type: "pdf" }
  | { type: "unsupported" };

const TEXT_CONTENT_TYPES: DataViewerContentType[] = [
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

  if (TEXT_CONTENT_TYPES.includes(contentType as DataViewerContentType)) {
    return { type: "text", dataViewerContentType: contentType as DataViewerContentType };
  }

  // Common YAML variation
  if (contentType === "application/x-yaml") {
    return { type: "text", dataViewerContentType: "application/yaml" };
  }

  // Other text/* types fallback to plain text
  if (contentType.startsWith("text/")) {
    return { type: "text", dataViewerContentType: "text/plain" };
  }

  // Images (except SVG which is handled above as text)
  if (contentType.startsWith("image/")) {
    return { type: "image" };
  }

  // PDF
  if (contentType === "application/pdf") {
    return { type: "pdf" };
  }

  return { type: "unsupported" };
}
