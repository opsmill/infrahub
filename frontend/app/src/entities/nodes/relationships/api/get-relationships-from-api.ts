import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

type GenerateRelationshipListQueryParams = PaginationParams & {
  peer: string;
  search?: string;
  filterQuery?: Record<string, string | number | boolean | string[]>;
  // Extra node fields to select (json-to-graphql-query form), so callers request
  // kind-specific fields without this builder knowing about any node kind.
  additionalFields?: Record<string, unknown>;
};

const isIdFilter = (filterName: string): boolean =>
  filterName === "ids" || filterName.endsWith("__ids");

const generateRelationshipListQuery = ({
  peer,
  filterQuery = {},
  additionalFields = {},
}: Pick<
  GenerateRelationshipListQueryParams,
  "peer" | "filterQuery" | "additionalFields"
>): string => {
  const filterArgs = Object.fromEntries(
    Object.entries(filterQuery).map(([filterName, value]) => [
      filterName,
      isIdFilter(filterName) ? new VariableType(filterName) : value,
    ])
  );

  const request = {
    query: {
      __name: "GetRelationshipList" + peer,
      __variables: {
        limit: "Int",
        offset: "Int",
        search: "String",
        ...Object.fromEntries(
          Object.keys(filterQuery)
            .filter(isIdFilter)
            .map((filterName) => [filterName, "[ID]"])
        ),
      },
      [peer]: {
        __args: {
          limit: new VariableType("limit"),
          offset: new VariableType("offset"),
          any__value: new VariableType("search"),
          partial_match: true,
          ...filterArgs,
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

export type getRelationshipsFromApiParams = ContextParams & GenerateRelationshipListQueryParams;

export const getRelationshipsFromApi = async ({
  peer,
  // The pagination and search bounds used to be inlined into the document with these
  // defaults; keep defaulting them here so omitted values still reach the API as 0 and
  // the empty string rather than null.
  limit = 0,
  offset = 0,
  search = "",
  branchName,
  atDate,
  filterQuery,
  additionalFields,
}: getRelationshipsFromApiParams) => {
  const query = graphql(generateRelationshipListQuery({ peer, filterQuery, additionalFields }));

  const idFilterVariables = Object.fromEntries(
    Object.entries(filterQuery ?? {}).filter(([filterName]) => isIdFilter(filterName))
  );

  return graphqlClient.query({
    query,
    variables: { limit, offset, search, ...idFilterVariables },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
