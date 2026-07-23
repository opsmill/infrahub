import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import type { PaginationParams } from "@/shared/api/types";

export type GenerateRelationshipListQueryParams = PaginationParams & {
  peer: string;
  search?: string;
  filterQuery?: Record<string, string | number | boolean | string[]>;
};

export const isIdFilter = (filterName: string): boolean =>
  filterName === "ids" || filterName.endsWith("__ids");

export const generateRelationshipListQuery = ({
  peer,
  filterQuery = {},
}: Pick<GenerateRelationshipListQueryParams, "peer" | "filterQuery">): string => {
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
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};
