import { gql } from "@apollo/client";

export const REMOVE_GROUP = gql`
  mutation RelationshipRemove($objectId: String!, $groupId: String!) {
    RelationshipRemove(
      data: { id: $objectId, name: "member_of_groups", nodes: [{ id: $groupId }] }
    ) {
      ok
    }
  }
`;
