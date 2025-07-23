import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { BranchContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";

const MUTATION = `
mutation ProposedChangeReview($id: String!, $decision: ProposedChangeApprovalDecision!) {
  CoreProposedChangeReview(data: {
    id: $id,
    decision: $decision
  }) {
    ok
  }
}
`;

export interface UpdateReviewFromApiApiParams extends BranchContextParams {
  proposedChangeId: string;
  decision: string;
}

export function updateReviewFromApi({
  proposedChangeId,
  decision,
  branchName,
}: UpdateReviewFromApiApiParams) {
  return graphqlClient.mutate({
    mutation: gql(MUTATION),
    variables: {
      id: proposedChangeId,
      decision,
    },
    context: {
      branch: branchName,
    },
  });
}
