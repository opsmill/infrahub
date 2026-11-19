import * as R from "remeda";

import type { ElevationItem } from "@/entities/rack-elevation/domain/model/elevation";
import type { Facet, ItemFilter } from "@/entities/rack-elevation/domain/model/filter";
import type { GraphNode, NodeStore, Schema } from "@/entities/rack-elevation/domain/model/schema";
import { getDisplayLabel } from "@/entities/rack-elevation/domain/rules/resolve-path";

const MAX_FACET_VALUES = 20;

interface FacetValue {
  label: string;
  value: string;
}

/** Values an object can be filtered on: its attributes, its peers and its peers' peers. */
export function getFacetValues(
  node: GraphNode,
  rackId: string,
  store: NodeStore,
  schema: Schema
): Record<string, FacetValue> {
  const values: Record<string, FacetValue> = {};
  const schemaKind = schema[node.kind];
  if (!schemaKind) return values;

  for (const attribute of schemaKind.attributes) {
    const value = node.attributes[attribute.name];
    if (value === null || value === undefined || value === "") continue;
    values[attribute.name] = { label: attribute.label, value: String(value) };
  }

  for (const relationship of schemaKind.relationships) {
    if (relationship.cardinality !== "one") continue;
    const peerId = node.relationships[relationship.name];
    const peer = typeof peerId === "string" && peerId !== rackId ? store[peerId] : undefined;
    if (!peer) continue;
    values[relationship.name] = { label: relationship.label, value: getDisplayLabel(peer, schema) };

    for (const nested of schema[peer.kind]?.relationships ?? []) {
      if (nested.cardinality !== "one") continue;
      const nestedId = peer.relationships[nested.name];
      const nestedPeer = typeof nestedId === "string" ? store[nestedId] : undefined;
      if (!nestedPeer) continue;
      values[`${relationship.name}.${nested.name}`] = {
        label: `${relationship.label} › ${nested.label}`,
        value: getDisplayLabel(nestedPeer, schema),
      };
    }
  }
  return values;
}

export function buildFacets(itemValues: Record<string, FacetValue>[]): Facet[] {
  const facets = new Map<string, { label: string; counts: Map<string, number>; total: number }>();

  for (const values of itemValues) {
    for (const [key, { label, value }] of Object.entries(values)) {
      const facet = facets.get(key) ?? { label, counts: new Map(), total: 0 };
      facet.counts.set(value, (facet.counts.get(value) ?? 0) + 1);
      facet.total += 1;
      facets.set(key, facet);
    }
  }

  return [...facets.entries()]
    .filter(([, facet]) => {
      const isAllUnique = facet.total > 1 && facet.counts.size === facet.total;
      return !isAllUnique && facet.counts.size <= MAX_FACET_VALUES;
    })
    .map(([key, facet]) => ({
      key,
      label: facet.label,
      values: [...facet.counts.entries()]
        .map(([value, count]) => ({ value, count }))
        .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value)),
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

export function matchesFilter(
  item: ElevationItem,
  values: Record<string, FacetValue>,
  filter: ItemFilter
): boolean {
  const conditionsByKey = R.groupBy(filter.conditions, (condition) => condition.key);
  for (const [key, conditions] of Object.entries(conditionsByKey)) {
    if (!conditions.some((condition) => values[key]?.value === condition.value)) return false;
  }

  const tokens = filter.query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return true;
  const haystack = [item.label, item.subtitle ?? "", ...Object.values(values).map((v) => v.value)]
    .join(" ")
    .toLowerCase();
  return tokens.every((token) => haystack.includes(token));
}
