import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/utils/constant";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addFiltersToRequest } from "@/shared/api/graphql/utils";
import { ContextParams } from "@/shared/api/types";
import { Filter } from "@/shared/hooks/useFilters";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

export type GetProposedChangesCountsParams = ContextParams & {
  filters?: Array<Filter>;
};

type GetProposedChangesCountsResult = {
  opened: number;
  closed: number;
};

export type GetProposedChangesCounts = (
  args: GetProposedChangesCountsParams
) => Promise<GetProposedChangesCountsResult>;

export const getProposedChangesCounts: GetProposedChangesCounts = async ({
  branchName,
  atDate,
  filters,
}) => {
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
  const { data } = await graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });

  const result = {
    opened: data.opened.count ?? 0,
    closed: data.closed.count ?? 0,
  };

  return result;
};
