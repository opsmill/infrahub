import { useSearchParams } from "react-router";

import type { Elevation } from "@/entities/rack-elevation/domain/model/elevation";
import { type ItemFilter, isFilterActive } from "@/entities/rack-elevation/domain/model/filter";
import {
  buildFacets,
  getFacetValues,
  matchesFilter,
} from "@/entities/rack-elevation/domain/rules/filter-items";
import { useRackElevationStore } from "@/entities/rack-elevation/ui/rack-elevation-store";

const QUERY_PARAM = "q";
const CONDITION_PARAM = "filter";
const CONDITION_SEPARATOR = "=";

export function useElevationFilter(elevation: Elevation | null) {
  const { nodes, schema } = useRackElevationStore();
  const [searchParams, setSearchParams] = useSearchParams();

  const filter: ItemFilter = {
    query: searchParams.get(QUERY_PARAM) ?? "",
    conditions: searchParams.getAll(CONDITION_PARAM).flatMap((raw) => {
      const index = raw.indexOf(CONDITION_SEPARATOR);
      return index > 0 ? [{ key: raw.slice(0, index), value: raw.slice(index + 1) }] : [];
    }),
  };

  const setFilter = (next: ItemFilter) => {
    setSearchParams(
      (current) => {
        const params = new URLSearchParams(current);
        params.delete(QUERY_PARAM);
        params.delete(CONDITION_PARAM);
        if (next.query) params.set(QUERY_PARAM, next.query);
        for (const { key, value } of next.conditions) {
          params.append(CONDITION_PARAM, `${key}${CONDITION_SEPARATOR}${value}`);
        }
        return params;
      },
      { replace: true }
    );
  };

  const items = elevation ? [...elevation.placed, ...elevation.unplaced] : [];
  const valuesByKey = new Map(
    items.map((item) => [
      item.key,
      getFacetValues(item.node, elevation?.rack.id ?? "", nodes, schema),
    ])
  );
  const matched = items.filter((item) =>
    matchesFilter(item, valuesByKey.get(item.key) ?? {}, filter)
  );

  return {
    filter,
    setFilter,
    facets: buildFacets([...valuesByKey.values()]),
    matchedKeys: isFilterActive(filter) ? new Set(matched.map((item) => item.key)) : null,
    matchCount: matched.length,
    totalCount: items.length,
  };
}
