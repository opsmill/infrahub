import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

type GenerateRelationshipListQueryParams = PaginationParams & {
  peer: string;
  parent?: { name?: string; value?: string };
  search?: string;
  filterQuery?: Record<string, string | number | boolean | string[]>;
  // Extra node fields to select (json-to-graphql-query form), so callers request
  // kind-specific fields without this builder knowing about any node kind.
  additionalFields?: Record<string, unknown>;
};

const generateRelationshipListQuery = ({
  peer,
  parent,
  filterQuery = {},
  additionalFields = {},
}: Omit<GenerateRelationshipListQueryParams, "limit" | "offset" | "search">): string => {
  const defaultArgs = {
    limit: new VariableType("limit"),
    offset: new VariableType("offset"),
    any__value: new VariableType("search"),
    partial_match: true,
  };

  const args =
    parent?.name && parent?.value
      ? { ...defaultArgs, [`${parent.name}__ids`]: [parent.value] }
      : { ...defaultArgs };

  const request = {
    query: {
      __name: "GetRelationshipList" + peer,
      __variables: {
        limit: "Int",
        offset: "Int",
        search: "String",
      },
      [peer]: {
        __args: {
          ...args,
          ...filterQuery,
        },
        edges: {
          node: {
            id: true,
            hfid: true,
            display_label: true,
            __typename: true,
            ...additionalFields,
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};

export type getRelationshipsFromApiParams = ContextParams &
  Omit<GenerateRelationshipListQueryParams, "parent">;

export const getRelationshipsFromApi = async ({
  peer,
  limit,
  offset,
  search,
  branchName,
  atDate,
  filterQuery,
  additionalFields,
}: getRelationshipsFromApiParams) => {
  const query = graphql(generateRelationshipListQuery({ peer, filterQuery, additionalFields }));

  return graphqlClient.query({
    query,
    variables: { limit, offset, search },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
