import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";

import type {
  GetPathTraversalParams,
  PathTraversalResponse,
} from "@/entities/path-traversal/domain/model/path-traversal";

const nodeFields = {
  id: true,
  kind: true,
  label: true,
  display_label: true,
  hfid: true,
};

const pathFields = {
  hops: {
    node: nodeFields,
    relationship: {
      from_rel: true,
      from_label: true,
      to_rel: true,
      to_label: true,
      kind: true,
    },
  },
  depth: true,
};

export async function getPathTraversalFromApi(params: GetPathTraversalParams) {
  const {
    sourceId,
    destinationId,
    maxDepth,
    maxPaths,
    kindFilter,
    relationshipFilter,
    excludedKinds,
    shortestPathsOnly,
    branchName,
    atDate,
  } = params;

  const dataArgs: Record<string, unknown> = {
    source_id: sourceId,
    destination_id: destinationId,
  };
  if (maxDepth !== undefined) dataArgs.max_depth = maxDepth;
  if (maxPaths !== undefined) dataArgs.max_paths = maxPaths;
  if (kindFilter?.length) dataArgs.kind_filter = kindFilter;
  if (relationshipFilter?.length) dataArgs.relationship_filter = relationshipFilter;
  if (excludedKinds?.length) dataArgs.excluded_kinds = excludedKinds;
  if (shortestPathsOnly !== undefined) dataArgs.shortest_paths_only = shortestPathsOnly;

  const queryString = jsonToGraphQLQuery({
    query: {
      __name: "GetPathTraversal",
      InfrahubPathTraversal: {
        __args: { data: dataArgs },
        paths: pathFields,
        source: nodeFields,
        destination: nodeFields,
        count: true,
        truncated_at_depth: true,
      },
    },
  });

  return graphqlClient.query<{ InfrahubPathTraversal: PathTraversalResponse }>({
    query: graphql(queryString),
    context: { branch: branchName, date: atDate },
  });
}
