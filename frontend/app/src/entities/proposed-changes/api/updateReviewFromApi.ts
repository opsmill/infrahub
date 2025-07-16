import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { BranchContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";

const MUTATION = `
mutation ProposedChangeReview($id: ID, $decison: String) {
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

export function udpateReviewFromApi({
  proposedChangeId,
  decision,
  branchName,
}: UpdateReviewFromApiApiParams) {
  return graphqlClient.mutate({
    mutation: gql(MUTATION),
    variables: {
      proposedChangeId,
      decision,
    },
    context: {
      branch: branchName,
    },
  });
}
