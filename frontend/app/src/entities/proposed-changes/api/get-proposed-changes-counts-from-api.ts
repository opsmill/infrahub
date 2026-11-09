import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import { addFiltersToRequest } from "@/shared/api/graphql/utils";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change";
import { PROPOSED_CHANGE_STATES } from "@/entities/proposed-changes/domain/model/proposed-change-state";

export interface ProposedChangesCountsFromApiParams {
  filters?: Array<Filter>;
}

export const getProposedChangesCountsFromApi = async ({
  filters,
}: ProposedChangesCountsFromApiParams) => {
  const query = graphql(
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
