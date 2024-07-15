import { gql } from "@apollo/client";

export const ADD_RELATIONSHIP = gql`
  mutation RelationshipAdd(
    $objectId: String!
    $relationshipName: String!
    $relationshipIds: [RelatedNodeInput]
  ) {
    RelationshipAdd(data: { id: $objectId, name: $relationshipName, nodes: $relationshipIds }) {
      ok
    }
  }
`;
