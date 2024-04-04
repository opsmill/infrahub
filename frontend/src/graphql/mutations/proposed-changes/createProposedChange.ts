import { gql } from "@apollo/client";

export const CREATE_PROPOSED_CHANGE = gql`
  mutation CoreProposedChangeCreate(
    $name: String!
    $description: String!
    $source_branch: String!
    $destination_branch: String!
    $reviewers: [RelatedNodeInput!]!
    $created_by: RelatedNodeInput!
  ) {
    CoreProposedChangeCreate(
      data: {
        name: { value: $name }
        description: { value: $description }
        source_branch: { value: $source_branch }
        destination_branch: { value: $destination_branch }
        reviewers: $reviewers
        created_by: $created_by
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
