import { PaginationParams } from "@/shared/api/types";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

export const generateRelationshipListQuery = ({
  peer,
  parent,
  limit = 0,
  offset = 0,
  search = "",
}: PaginationParams & {
  peer: string;
  parent?: { name?: string; value?: string };
  search?: string;
}): string => {
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
        },
        count: true,
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
