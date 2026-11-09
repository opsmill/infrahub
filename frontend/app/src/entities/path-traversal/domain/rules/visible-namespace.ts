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
