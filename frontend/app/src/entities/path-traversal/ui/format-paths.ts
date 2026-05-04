import type { PathResult, PathTraversalResponse } from "../domain/get-path-traversal";
import { formatRelName } from "./utils";

export function formatPathAsText(data: PathTraversalResponse, pathIndex: number): string {
  const path = data.paths[pathIndex];
  if (!path) return "";
  const objectLabels = path.objects.map((o) => o.display_label);
  const parts: string[] = [];
  for (let i = 0; i < objectLabels.length; i++) {
    parts.push(objectLabels[i] ?? "");
    if (i < objectLabels.length - 1) {
      const rel = path.relationships[i];
      if (rel) {
        parts.push(`-[${formatRelName(rel.name)}]->`);
      } else {
        parts.push(" -> ");
      }
    }
  }
  return parts.join(" ");
}

export function copyAllPathsAsText(data: PathTraversalResponse): string {
  return data.paths
    .map((path, i) => `Path ${i + 1}: ${path.objects.map((o) => o.display_label).join(" → ")}`)
    .join("\n");
}

export function pathPreview(path: PathResult, maxObjects = 3): string {
  const names = path.objects.map((o) => o.display_label);
  if (names.length <= maxObjects) return names.join(" -> ");
  const first = names[0];
  const last = names.at(-1);
  return `${first} -> ... -> ${last}`;
}

export function getKindCounts(path: PathResult): string {
  const counts = new Map<string, number>();
  for (const object of path.objects) {
    counts.set(object.kind, (counts.get(object.kind) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([kind, count]) => `${count}x ${kind}`)
    .join(", ");
}
