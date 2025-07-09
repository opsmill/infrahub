import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";

////////////////////////////////////////////////////////////////////////////////////////////////////

const GET_PROPOSED_CHANGES_COUNTS = `
query GET_PROPOSED_CHANGES_COUNTS {
    opened: CoreProposedChange(state__values: ["open"]) {
      count
    }
    closed: CoreProposedChange(state__values: ["closed", "merged", "canceled"]) {
      count
    }
  }
`;

////////////////////////////////////////////////////////////////////////////////////////////////////

export type GetProposedChangesCountsParams = ContextParams;

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
}) => {
  const query = gql(GET_PROPOSED_CHANGES_COUNTS);
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
