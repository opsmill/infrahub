import type { DataViewerContentType } from "@/shared/components/data-viewer/types";

type TextViewerType = {
  type: "text";
  dataViewerContentType: DataViewerContentType;
};

type EmbedViewerType = {
  type: "image" | "pdf";
};

type UnsupportedViewerType = {
  type: "unsupported";
};

export type ViewerType = TextViewerType | EmbedViewerType | UnsupportedViewerType;

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

  // Text-based content (including SVG which is text-based XML)
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
