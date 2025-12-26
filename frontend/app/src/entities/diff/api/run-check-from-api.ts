import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const RUN_CHECK = graphql(`
  mutation RUN_CHECK($proposedChangeId: String!, $checkType: CheckType) {
    CoreProposedChangeRunCheck(data: { id: $proposedChangeId, check_type: $checkType }) {
      ok
    }
  }
`);

export interface RunCheckFromApiParams extends VariablesOf<typeof RUN_CHECK> {}

export const runCheckFromApi = ({ proposedChangeId, checkType }: RunCheckFromApiParams) => {
  return graphqlClient.mutate({
    mutation: RUN_CHECK,
    variables: {
      proposedChangeId,
      checkType,
    },
  });
};
