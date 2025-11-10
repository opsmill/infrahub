import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addFiltersToRequest } from "@/shared/api/graphql/utils";
import type { Filter } from "@/shared/hooks/useFilters";

import {
  PROPOSED_CHANGE_OBJECT,
  PROPOSED_CHANGE_STATES,
} from "@/entities/proposed-changes/constants";

export interface ProposedChangesCountsFromApiParams {
  filters?: Array<Filter>;
}

export const getProposedChangesCountsFromApi = async ({
  filters,
}: ProposedChangesCountsFromApiParams) => {
  const query = gql(
    jsonToGraphQLQuery({
      query: {
        __name: "GET_PROPOSED_CHANGE_COUNTS",
        opened: {
          __aliasFor: PROPOSED_CHANGE_OBJECT,
          __args: {
            ...(filters ? addFiltersToRequest(filters) : {}),
            state__values: PROPOSED_CHANGE_STATES.opened,
          },
          count: true,
        },
        closed: {
          __aliasFor: PROPOSED_CHANGE_OBJECT,
          __args: {
            ...(filters ? addFiltersToRequest(filters) : {}),
            state__values: PROPOSED_CHANGE_STATES.closed,
          },
          count: true,
        },
      },
    })
  );

  return graphqlClient.query({
    query,
  });
};
