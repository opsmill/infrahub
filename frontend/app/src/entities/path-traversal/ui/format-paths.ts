import type { PathTraversalResponse } from "../domain/path-traversal.types";

export function formatPathAsText(data: PathTraversalResponse, pathIndex: number): string {
  const path = data.paths[pathIndex];
  if (!path) return "";

  return path.hops
    .map((hop, index) => {
      const label = hop.node.display_label;
      if (index === 0) return label;
      const rel = hop.relationship?.from_label;
      return rel ? `-[${rel}]-> ${label}` : `-> ${label}`;
    })
    .join(" ");
}

export function copyAllPathsAsText(data: PathTraversalResponse): string {
  return data.paths
    .map(
      (path, i) => `Path ${i + 1}: ${path.hops.map((hop) => hop.node.display_label).join(" → ")}`
    )
    .join("\n");
}
