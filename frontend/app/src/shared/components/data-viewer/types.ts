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
