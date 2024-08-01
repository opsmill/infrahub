import { gql } from "@/generated";

export const DELETE_PROPOSED_CHANGE = gql(/* GraphQL */ `
  mutation CoreProposedChangeDelete($id: String!) {
    CoreProposedChangeDelete(data: { id: $id }) {
      ok
    }
  }
`);
