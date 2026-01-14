import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const MUTATION = graphql(`
  mutation ProposedChangeReview($proposedChangeId: String!, $decision: ProposedChangeApprovalDecision!) {
    CoreProposedChangeReview(data: { id: $proposedChangeId, decision: $decision }) {
      ok
    }
  }
`);

export interface UpdateProposedChangeReviewFromApiParams extends VariablesOf<typeof MUTATION> {}

export function updateProposedChangeReviewFromApi({
  proposedChangeId,
  decision,
}: UpdateProposedChangeReviewFromApiParams) {
  return graphqlClient.mutate({
    mutation: MUTATION,
    variables: {
      proposedChangeId,
      decision,
    },
  });
}
