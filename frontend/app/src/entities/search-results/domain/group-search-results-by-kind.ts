import type { SearchResultsGroup } from "@/entities/search-results/types";

export function groupSearchResultsByKind(
  results: Array<{ id: string; kind: string }>
): SearchResultsGroup[] {
  const groupMap = new Map<string, { kind: string; ids: string[] }>();
  for (const result of results) {
    const existing = groupMap.get(result.kind);
    if (existing) {
      existing.ids.push(result.id);
    } else {
      groupMap.set(result.kind, { kind: result.kind, ids: [result.id] });
    }
  }

  return Array.from(groupMap.values())
    .map((group) => ({
      kind: group.kind,
      label: group.kind,
      count: group.ids.length,
      results: group.ids.map((id) => ({ id, kind: group.kind })),
    }))
    .sort((a, b) => b.count - a.count);
}
