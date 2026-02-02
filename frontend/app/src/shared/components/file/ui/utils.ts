import type { DataViewerContentType } from "@/shared/components/data-viewer/types";

export function mapToDataViewerContentType(contentType?: string): DataViewerContentType | null {
  if (!contentType) return null;

  const supportedTypes: DataViewerContentType[] = [
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

  // Check for exact match
  if (supportedTypes.includes(contentType as DataViewerContentType)) {
    return contentType as DataViewerContentType;
  }

  // Map common variations
  if (contentType === "application/x-yaml") return "application/yaml";
  if (contentType.startsWith("text/")) return "text/plain";

  return null;
}
