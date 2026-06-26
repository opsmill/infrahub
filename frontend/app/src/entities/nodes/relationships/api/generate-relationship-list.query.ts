import { jsonToGraphQLQuery } from "json-to-graphql-query";

import type { PaginationParams } from "@/shared/api/types";

export type GenerateRelationshipListQueryParams = PaginationParams & {
  peer: string;
  parent?: { name: string; value: string };
  search?: string;
  filterQuery?: Record<string, string | number | boolean | string[]>;
  // Extra node fields to select (json-to-graphql-query form), so callers request
  // kind-specific fields without this builder knowing about any node kind.
  additionalFields?: Record<string, unknown>;
};

export const generateRelationshipListQuery = ({
  peer,
  parent,
  limit = 0,
  offset = 0,
  search = "",
  filterQuery = {},
  additionalFields = {},
}: GenerateRelationshipListQueryParams): string => {
  const defaultArgs = { limit, offset, any__value: search, partial_match: true };

  const args = parent?.value
    ? { ...defaultArgs, [`${parent.name}__ids`]: [parent.value] }
    : { ...defaultArgs };

  const request = {
    query: {
      __name: "GetRelationshipList" + peer,
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
