import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

export interface ConvertObjectFromApiApiParams extends BranchContextParams {
  data: Record<string, any>;
}

export function convertObjectFromApi({ data, branchName }: ConvertObjectFromApiApiParams) {
  const mutation = gql`
    mutation {
      ConvertObjectType(
        data: {
          fields_mapping: $data
        }
      ) {
        ok
      }
    }
  }`;

  return graphqlClient.mutate({
    mutation,
    context: {
      branch: branchName,
    },
    variables: {
      data,
    },
  });
}
