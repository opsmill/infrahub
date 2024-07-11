import { gql } from "@apollo/client";

export const ADD_GROUPS = gql`
  mutation RelationshipAdd($objectId: String!, $groupIds: [RelatedNodeInput]) {
    RelationshipAdd(data: { id: $objectId, name: "member_of_groups", nodes: $groupIds }) {
      ok
    }
  }
`;
