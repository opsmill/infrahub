import { gql } from "@apollo/client";

import { CheckType } from "@/shared/api/graphql/generated/graphql";
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

export type UpdateCheckFromApiParams = {
  proposedChangeId: string;
  checkType: CheckType;
};

export const runCheckFromApi = ({ proposedChangeId, checkType }: UpdateCheckFromApiParams) => {
  return graphqlClient.mutate({
    mutation: RUN_CHECK,
    variables: {
      proposedChangeId,
      checkType,
    },
  });
};
