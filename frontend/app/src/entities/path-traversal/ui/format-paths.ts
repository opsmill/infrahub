import type { PathResult, PathTraversalResponse } from "../domain/path-traversal.types";

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

export function pathPreview(path: PathResult, maxHops = 3): string {
  const names = path.hops.map((hop) => hop.node.display_label);
  if (names.length <= maxHops) return names.join(" -> ");
  return `${names[0]} -> ... -> ${names.at(-1)}`;
}

export function getKindCounts(path: PathResult): string {
  const counts = new Map<string, number>();
  for (const hop of path.hops) {
    counts.set(hop.node.kind, (counts.get(hop.node.kind) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([kind, count]) => `${count}x ${kind}`)
    .join(", ");
}
