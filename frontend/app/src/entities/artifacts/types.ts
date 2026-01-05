export type ArtifactStatus = "Error" | "Pending" | "Processing" | "Ready";

export type ArtifactContentType =
  | "application/json"
  | "application/yaml"
  | "application/hcl"
  | "image/svg+xml"
  | "text/plain"
  | "text/markdown"
  | "application/xml"
  | "text/csv";
