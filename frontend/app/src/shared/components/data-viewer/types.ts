/**
 * Text MIME content types that render as code/text.
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
 * Image MIME content types that render as images.
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
 */
export type DataViewerContentType = TextContentType | ImageContentType | PdfContentType;

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

export function isTextContentType(contentType?: string): contentType is TextContentType {
  return TEXT_CONTENT_TYPES.includes(contentType as TextContentType);
}

export function isImageContentType(contentType?: string): contentType is ImageContentType {
  return IMAGE_CONTENT_TYPES.includes(contentType as ImageContentType);
}

export function isPdfContentType(contentType?: string): contentType is PdfContentType {
  return contentType === "application/pdf";
}

export function getExtensionFromContentType(contentType?: string): string {
  switch (contentType) {
    case "application/json":
      return "json";
    case "application/yaml":
    case "application/x-yaml":
      return "yaml";
    case "application/hcl":
      return "hcl";
    case "application/graphql":
      return "graphql";
    case "application/xml":
      return "xml";
    case "image/svg+xml":
      return "svg";
    case "text/markdown":
      return "md";
    case "text/csv":
      return "csv";
    case "application/pdf":
      return "pdf";
    case "image/png":
      return "png";
    case "image/jpeg":
      return "jpg";
    case "image/gif":
      return "gif";
    case "image/webp":
      return "webp";
    case "image/bmp":
      return "bmp";
    case "image/x-icon":
      return "ico";
    default:
      return "txt";
  }
}
