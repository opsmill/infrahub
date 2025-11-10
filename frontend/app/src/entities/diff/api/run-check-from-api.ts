import { gql } from "@apollo/client";

import type {
  Run_CheckMutation,
  Run_CheckMutationVariables,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const RUN_CHECK = gql`
  mutation RUN_CHECK($proposedChangeId: String!, $checkType: CheckType) {
    CoreProposedChangeRunCheck (
      data: {
        id: $proposedChangeId,
        check_type: $checkType
      }
    ) {
      ok
    }
  }
`;

export interface RunCheckFromApiParams extends Run_CheckMutationVariables {}

export const runCheckFromApi = ({ proposedChangeId, checkType }: RunCheckFromApiParams) => {
  return graphqlClient.mutate<Run_CheckMutation, Run_CheckMutationVariables>({
    mutation: RUN_CHECK,
    variables: {
      proposedChangeId,
      checkType,
    },
  });
};
