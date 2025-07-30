import {
  PROPOSED_CHANGE_OBJECT,
  PROPOSED_CHANGE_STATES,
} from "@/entities/proposed-changes/constants";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addFiltersToRequest } from "@/shared/api/graphql/utils";
import { ContextParams } from "@/shared/api/types";
import { Filter } from "@/shared/hooks/useFilters";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

export interface ProposedChangesCountsFromApiParams extends ContextParams {
  filters?: Array<Filter>;
}

export const getProposedChangesCountsFromApi = async ({
  branchName,
  atDate,
  filters,
}: ProposedChangesCountsFromApiParams) => {
  const query = gql(
    jsonToGraphQLQuery({
      query: {
        opened: {
          __aliasFor: PROPOSED_CHANGE_OBJECT,
          __args: {
            ...(filters ? addFiltersToRequest(filters) : {}),
            state__values: PROPOSED_CHANGE_STATES.opened,
            is_draft__value: false,
          },
          count: true,
        },
        draft: {
          __aliasFor: PROPOSED_CHANGE_OBJECT,
          __args: {
            ...(filters ? addFiltersToRequest(filters) : {}),
            is_draft__value: true,
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
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
