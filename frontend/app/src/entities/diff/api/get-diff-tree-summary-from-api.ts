import { gql } from "@apollo/client";

import type {
  Get_Diff_Tree_SummaryQuery,
  Get_Diff_Tree_SummaryQueryVariables,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const GET_PROPOSED_CHANGES_DIFF_SUMMARY = gql`
  query GET_DIFF_TREE_SUMMARY($branch: String, $filters: DiffTreeQueryFilters) {
    DiffTreeSummary(branch: $branch, filters: $filters) {
      num_added
      num_updated
      num_removed
      num_conflicts
    }
  }
`;

export interface GetDiffTreeSummaryFromApiParams extends Get_Diff_Tree_SummaryQueryVariables {}

export function getDiffTreeSummaryFromApi(variables: Get_Diff_Tree_SummaryQueryVariables) {
  return graphqlClient.query<Get_Diff_Tree_SummaryQuery, Get_Diff_Tree_SummaryQueryVariables>({
    query: GET_PROPOSED_CHANGES_DIFF_SUMMARY,
    variables,
    context: {
      processErrorMessage: () => {},
    },
  });
}
