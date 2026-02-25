import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_BRANCHES_COUNT = graphql(`
  query GetBranchesCount($nameValue: String, $partialMatch: Boolean, $statusValue: BranchStatus, $createdById: ID, $branchedFromAfter: DateTime, $branchedFromBefore: DateTime, $createdAtAfter: DateTime, $createdAtBefore: DateTime, $updatedAtAfter: DateTime, $updatedAtBefore: DateTime) {
    InfrahubBranch(name__value: $nameValue, partial_match: $partialMatch, status__value: $statusValue, node_metadata__created_by__id: $createdById, branched_from__after: $branchedFromAfter, branched_from__before: $branchedFromBefore, node_metadata__created_at__after: $createdAtAfter, node_metadata__created_at__before: $createdAtBefore, node_metadata__updated_at__after: $updatedAtAfter, node_metadata__updated_at__before: $updatedAtBefore) {
      count
    }
  }
`);

export type GetBranchesCountFromApiParams = VariablesOf<typeof GET_BRANCHES_COUNT>;

export const getBranchesCountFromApi = async ({
  nameValue,
  partialMatch,
  statusValue,
  createdById,
  branchedFromAfter,
  branchedFromBefore,
  createdAtAfter,
  createdAtBefore,
  updatedAtAfter,
  updatedAtBefore,
}: GetBranchesCountFromApiParams = {}) => {
  return graphqlClient.query({
    query: GET_BRANCHES_COUNT,
    variables: {
      nameValue,
      partialMatch,
      statusValue,
      createdById,
      branchedFromAfter,
      branchedFromBefore,
      createdAtAfter,
      createdAtBefore,
      updatedAtAfter,
      updatedAtBefore,
    },
  });
};
