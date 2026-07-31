import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const CREATE_PROPOSED_CHANGE = graphql(`
  mutation CoreProposedChangeCreate(
    $name: String!
    $isDraft: Boolean
    $description: String
    $source_branch: String!
    $destination_branch: String!
    $reviewers: [RelatedNodeInput!]
  ) {
    CoreProposedChangeCreate(
      data: {
        name: { value: $name }
        is_draft: { value: $isDraft }
        description: { value: $description }
        source_branch: { value: $source_branch }
        destination_branch: { value: $destination_branch }
        reviewers: $reviewers
      }
    ) {
      object {
        id
        display_label
      }
      ok
    }
  }
`);

export interface CreateProposedChangeFromApiParams
  extends VariablesOf<typeof CREATE_PROPOSED_CHANGE> {}

export function createProposedChangeFromApi(variables: CreateProposedChangeFromApiParams) {
  return graphqlClient.mutate({
    mutation: CREATE_PROPOSED_CHANGE,
    variables,
  });
}
