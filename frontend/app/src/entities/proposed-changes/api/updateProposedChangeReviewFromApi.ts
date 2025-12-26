import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const MUTATION = graphql(`
  mutation ProposedChangeReview($id: String!, $decision: ProposedChangeApprovalDecision!) {
    CoreProposedChangeReview(data: { id: $id, decision: $decision }) {
      ok
    }
  }
`);

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
    } satisfies VariablesOf<typeof MUTATION>,
  });
}
