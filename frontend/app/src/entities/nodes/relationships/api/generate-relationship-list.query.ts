import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import type { PaginationParams } from "@/shared/api/types";

export type GenerateRelationshipListQueryParams = PaginationParams & {
  peer: string;
  parent?: { name?: string; value?: string };
  search?: string;
  filterQuery?: Record<string, string | number | boolean | string[]>;
};

export const generateRelationshipListQuery = ({
  peer,
  parent,
  filterQuery = {},
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
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};
