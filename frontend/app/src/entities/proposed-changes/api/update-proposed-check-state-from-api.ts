import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";

const MUTATION = gql`
  mutation ProposedChangeCheckForApprovalRevoke($id: String!){
    CoreProposedChangeCheckForApprovalRevoke(
      data:  {
      ids: [$id]
      }
    ){
      ok
    }
  }
`;

export interface updateProposedChangeCheckStateFromApiParams {
  proposedChangeId: string;
}

export function updateProposedChangeCheckStateFromApi({
  proposedChangeId,
}: updateProposedChangeCheckStateFromApiParams) {
  return graphqlClient.mutate({
    mutation: MUTATION,
    variables: {
      id: proposedChangeId,
    },
  });
}
