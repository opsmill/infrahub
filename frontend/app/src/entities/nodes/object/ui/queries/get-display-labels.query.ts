import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { useMemo } from "react";

import { nodeCoreFragment } from "@/shared/api/graphql/fragments";
import useQuery from "@/shared/api/graphql/useQuery";
import { CONFIG } from "@/shared/config/config";

import type { NodeCore } from "@/entities/nodes/types";

const EMPTY_QUERY = gql`
  query GetDisplayLabelsByKindEmpty {
    __typename
  }
`;

type DisplayLabelRef = {
  id: string;
  kind: string;
};

type UseDisplayLabelsParams = {
  items: ReadonlyArray<DisplayLabelRef | null | undefined>;
  branch?: string | null;
  date?: Date | null;
};

// Groups (kind, id) pairs and resolves all display labels through a single
// GraphQL operation that aliases one root field per kind. Used to avoid
// firing one query per related node when rendering large lists (see #9067).
export function useDisplayLabels({ items, branch, date }: UseDisplayLabelsParams) {
  const groups = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const item of items) {
      if (!item?.id || !item.kind) continue;
      const existing = map.get(item.kind);
      if (existing) {
        if (!existing.includes(item.id)) existing.push(item.id);
      } else {
        map.set(item.kind, [item.id]);
      }
    }
    return map;
  }, [items]);

  const kinds = useMemo(() => Array.from(groups.keys()), [groups]);

  const queryDocument = useMemo(() => {
    if (groups.size === 0) return null;

    const queryObj: Record<string, unknown> = {
      __name: "GetDisplayLabelsByKind",
    };

    for (const [kind, ids] of groups.entries()) {
      queryObj[kind] = {
        __args: { ids },
        edges: {
          node: { ...nodeCoreFragment },
        },
      };
    }

    return gql(jsonToGraphQLQuery({ query: queryObj }));
  }, [groups]);

  const queryContext = useMemo(() => {
    if (branch === undefined && date === undefined) return;
    return { uri: CONFIG.GRAPHQL_URL(branch ?? null, date ?? null) };
  }, [branch, date]);

  const { data, loading, error } = useQuery(queryDocument ?? EMPTY_QUERY, {
    skip: !queryDocument,
    context: queryContext,
  });

  const labels = useMemo(() => {
    const result = new Map<string, NodeCore>();
    if (!data) return result;

    for (const kind of kinds) {
      const edges = data?.[kind]?.edges ?? [];
      for (const edge of edges) {
        const node = edge?.node;
        if (node?.id) result.set(node.id, node as NodeCore);
      }
    }
    return result;
  }, [data, kinds]);

  return { labels, loading, error };
}
