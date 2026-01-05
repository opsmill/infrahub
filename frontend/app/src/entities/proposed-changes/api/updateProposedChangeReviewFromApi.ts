import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const MUTATION = gql`
  mutation ProposedChangeReview($id: String!, $decision: ProposedChangeApprovalDecision!) {
    CoreProposedChangeReview(data: {
      id: $id,
      decision: $decision
    }) {
      ok
    }
  }
`;

export interface UpdateProposedChangeReviewFromApiParams {
  proposedChangeId: string;
  decision: string;
}

export function updateProposedChangeReviewFromApi({
  proposedChangeId,
  decision,
}: UpdateProposedChangeReviewFromApiParams) {
  return graphqlClient.mutate({
    mutation: MUTATION,
    variables: {
      id: proposedChangeId,
      decision,
    },
  });
}
