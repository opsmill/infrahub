import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";

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

export interface UpdateReviewFromApiApiParams {
  proposedChangeId: string;
  decision: string;
}

export function updateProposedCHangeReviewFromApi({
  proposedChangeId,
  decision,
}: UpdateReviewFromApiApiParams) {
  return graphqlClient.mutate({
    mutation: MUTATION,
    variables: {
      id: proposedChangeId,
      decision,
    },
  });
}
