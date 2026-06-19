import { jsonToGraphQLQuery } from "json-to-graphql-query";

import type { PaginationParams } from "@/shared/api/types";

import { IP_ADDRESS_POOL } from "@/entities/resource-manager/constants";

export type GenerateRelationshipListQueryParams = PaginationParams & {
  peer: string;
  parent?: { name: string; value: string };
  search?: string;
  filterQuery?: Record<string, string | number | boolean | string[]>;
};

export const generateRelationshipListQuery = ({
  peer,
  parent,
  limit = 0,
  offset = 0,
  search = "",
  filterQuery = {},
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
            // Only IP address pools surface a prefix-length override (the placeholder
            // shows this default); other pool kinds don't need it fetched.
            ...(peer === IP_ADDRESS_POOL && {
              default_prefix_length: { value: true },
            }),
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};
