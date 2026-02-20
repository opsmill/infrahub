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
 * Includes well-known types plus any arbitrary MIME type string.
 */
export type DataViewerContentType =
  | TextContentType
  | ImageContentType
  | PdfContentType
  | (string & {});

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
