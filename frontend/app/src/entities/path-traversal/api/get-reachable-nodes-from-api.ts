import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import type {
  GetReachableObjectsParams,
  ReachableObjectsResponse,
} from "@/entities/path-traversal/domain/path-traversal.types";

const pathFields = {
  objects: {
    __aliasFor: "nodes",
    id: true,
    kind: true,
    display_label: true,
  },
  relationships: { id: true, name: true, direction: true },
  depth: true,
};

export async function getReachableObjectsFromApi(params: GetReachableObjectsParams) {
  const { sourceId, targetKinds, maxDepth, maxResults, branchName, atDate } = params;

  const dataArgs: Record<string, unknown> = {
    source_id: sourceId,
    target_kinds: targetKinds,
  };
  if (maxDepth !== undefined) dataArgs.max_depth = maxDepth;
  if (maxResults !== undefined) dataArgs.max_results = maxResults;

  const queryString = jsonToGraphQLQuery({
    query: {
      __name: "GetReachableObjects",
      InfrahubReachableNodes: {
        __args: { data: dataArgs },
        source: { id: true, kind: true, display_label: true },
        reachable_objects: {
          __aliasFor: "reachable_nodes",
          id: true,
          kind: true,
          display_label: true,
          depth: true,
          relationship_name: true,
          path: pathFields,
        },
        paths: pathFields,
        total_found: true,
      },
    },
  });

  return graphqlClient.query<{ InfrahubReachableNodes: ReachableObjectsResponse }>({
    query: gql(queryString),
    context: { branch: branchName, date: atDate },
  });
}
