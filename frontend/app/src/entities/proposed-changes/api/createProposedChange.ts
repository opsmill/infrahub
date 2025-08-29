import { gql } from "@apollo/client";

export const CREATE_PROPOSED_CHANGE = gql`
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
`;
