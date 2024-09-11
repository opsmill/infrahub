import { gql } from "@apollo/client";

export const DELETE_PROPOSED_CHANGE = gql`
  mutation CoreProposedChangeDelete($id: String!) {
    CoreProposedChangeDelete(data: { id: $id }) {
      ok
    }
  }
`;
