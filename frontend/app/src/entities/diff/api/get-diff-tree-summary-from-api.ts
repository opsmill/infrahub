import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_PROPOSED_CHANGES_DIFF_SUMMARY = graphql(`
  query GET_DIFF_TREE_SUMMARY($branch: String, $filters: DiffTreeQueryFilters) {
    DiffTreeSummary(branch: $branch, filters: $filters) {
      num_added
      num_updated
      num_removed
      num_conflicts
    }
  }
`);

export type GetDiffTreeSummaryFromApiParams = VariablesOf<typeof GET_PROPOSED_CHANGES_DIFF_SUMMARY>;

export function getDiffTreeSummaryFromApi(variables: GetDiffTreeSummaryFromApiParams) {
  return graphqlClient.query({
    query: GET_PROPOSED_CHANGES_DIFF_SUMMARY,
    variables,
    context: {
      processErrorMessage: () => {},
    },
  });
}
