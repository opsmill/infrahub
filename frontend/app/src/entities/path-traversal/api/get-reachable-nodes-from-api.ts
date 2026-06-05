import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import type {
  GetReachableNodesParams,
  ReachableNodesResponse,
} from "@/entities/path-traversal/domain/path-traversal.types";

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

export async function getReachableNodesFromApi(params: GetReachableNodesParams) {
  const { sourceId, targetKinds, maxDepth, maxResults, maxPaths, branchName, atDate } = params;

  const dataArgs: Record<string, unknown> = {
    source_id: sourceId,
    target_kinds: targetKinds,
  };
  if (maxDepth !== undefined) dataArgs.max_depth = maxDepth;
  if (maxResults !== undefined) dataArgs.max_results = maxResults;
  if (maxPaths !== undefined) dataArgs.max_paths = maxPaths;

  const queryString = jsonToGraphQLQuery({
    query: {
      __name: "GetReachableNodes",
      InfrahubReachableNodes: {
        __args: { data: dataArgs },
        source: nodeFields,
        dependencies: {
          node: nodeFields,
          depth: true,
          path: pathFields,
        },
        count: true,
      },
    },
  });

  return graphqlClient.query<{ InfrahubReachableNodes: ReachableNodesResponse }>({
    query: gql(queryString),
    context: { branch: branchName, date: atDate },
  });
}
