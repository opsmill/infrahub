export type BreadcrumbItem =
  | { type: "select"; value: string; kind: string }
  | { type: "link"; label: string; to: string }
  | { type: "branch"; value: string }
  | { type: "display"; value: string; kind: string };
