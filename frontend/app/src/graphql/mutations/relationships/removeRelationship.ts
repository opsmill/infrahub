import Handlebars from "handlebars";
import { gql } from "@apollo/client";

export const removeRelationship = Handlebars.compile(`
mutation RelationshipRemove {
  RelationshipRemove (data: {{{data}}}) {
      ok
  }
}
`);

export const REMOVE_RELATIONSHIP = gql`
  mutation RelationshipRemove(
    $objectId: String!
    $relationshipName: String!
    $relationshipIds: [RelatedNodeInput]
  ) {
    RelationshipRemove(data: { id: $objectId, name: $relationshipName, nodes: $relationshipIds }) {
      ok
    }
  }
`;
