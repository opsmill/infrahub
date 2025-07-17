import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constant";
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
  const queryString = jsonToGraphQLQuery({
    query: {
      opened: {
        __aliasFor: PROPOSED_CHANGE_OBJECT,
        __args: {
          ...(filters ? addFiltersToRequest(filters) : {}),
          state__values: ["open"],
        },
        count: true,
      },
      closed: {
        __aliasFor: PROPOSED_CHANGE_OBJECT,
        __args: {
          ...(filters ? addFiltersToRequest(filters) : {}),
          state__values: ["closed", "merged", "canceled"],
        },
        count: true,
      },
    },
  });

  const query = gql(queryString);

  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
