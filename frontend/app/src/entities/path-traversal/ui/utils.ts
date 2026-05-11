const KIND_COLORS = [
  "#8b5cf6", // violet
  "#06b6d4", // cyan
  "#f59e0b", // amber
  "#ec4899", // pink
  "#14b8a6", // teal
  "#6366f1", // indigo
  "#84cc16", // lime
  "#f43f5e", // rose
];

export function getKindColor(kind: string): string {
  let hash = 0;
  for (const char of kind) {
    hash = hash * 31 + char.charCodeAt(0);
  }
  return KIND_COLORS[Math.abs(hash) % KIND_COLORS.length] as string;
}

// Mirrors backend/infrahub/core/query/path.py:35 (DEFAULT_EXCLUDED_NAMESPACES).
// Path traversal always excludes these on the server; we hide them in the UI to avoid
// surfacing kinds that would silently produce no results. Keep in sync with the backend.
export const HIDDEN_NAMESPACES = new Set([
  "Core",
  "Internal",
  "Builtin",
  "Lineage",
  "Profile",
  "Template",
]);

export const isVisibleNamespace = (namespace: string) => !HIDDEN_NAMESPACES.has(namespace);
