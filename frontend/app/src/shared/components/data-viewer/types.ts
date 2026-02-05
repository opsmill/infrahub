/**
 * Text MIME content types for DataViewer component.
 * Used to determine how content is rendered (code viewer, markdown, SVG, etc.)
 */
export type TextContentType =
  | "application/json"
  | "application/yaml"
  | "application/x-yaml"
  | "application/hcl"
  | "application/graphql"
  | "image/svg+xml"
  | "text/plain"
  | "text/markdown"
  | "application/xml"
  | "text/csv";

/**
 * Image MIME content types supported by DataViewer.
 */
export type ImageContentType =
  | "image/png"
  | "image/jpeg"
  | "image/gif"
  | "image/webp"
  | "image/bmp"
  | "image/x-icon";

/**
 * PDF MIME content type.
 */
export type PdfContentType = "application/pdf";

/**
 * All supported content types for DataViewer.
 * Use this type for props that accept content type to enable autocomplete.
 */
export type DataViewerContentType = TextContentType | ImageContentType | PdfContentType;

/**
 * Viewer type determined from content type.
 * - text: Renderable text content (code, markdown, csv, svg)
 * - image: Binary image content (png, jpeg, gif, etc.)
 * - pdf: PDF document
 * - unsupported: Content type not supported for preview
 */
export type ViewerType =
  | { type: "text"; textContentType: TextContentType }
  | { type: "image"; imageContentType: ImageContentType | (string & {}) }
  | { type: "pdf" }
  | { type: "unsupported" };

const TEXT_CONTENT_TYPES: TextContentType[] = [
  "application/json",
  "application/yaml",
  "application/x-yaml",
  "application/hcl",
  "application/graphql",
  "image/svg+xml",
  "text/plain",
  "text/markdown",
  "application/xml",
  "text/csv",
];

const IMAGE_CONTENT_TYPES: ImageContentType[] = [
  "image/png",
  "image/jpeg",
  "image/gif",
  "image/webp",
  "image/bmp",
  "image/x-icon",
];

export function getViewerType(contentType?: DataViewerContentType): ViewerType {
  if (!contentType) {
    return { type: "text", textContentType: "text/plain" };
  }

  if (TEXT_CONTENT_TYPES.includes(contentType as TextContentType)) {
    return { type: "text", textContentType: contentType as TextContentType };
  }

  // Other text/* types fallback to plain text
  if (contentType.startsWith("text/")) {
    return { type: "text", textContentType: "text/plain" };
  }

  // Images (except SVG which is handled above as text)
  if (contentType.startsWith("image/")) {
    return {
      type: "image",
      imageContentType: IMAGE_CONTENT_TYPES.includes(contentType as ImageContentType)
        ? (contentType as ImageContentType)
        : contentType,
    };
  }

  // PDF
  if (contentType === "application/pdf") {
    return { type: "pdf" };
  }

  return { type: "unsupported" };
}
