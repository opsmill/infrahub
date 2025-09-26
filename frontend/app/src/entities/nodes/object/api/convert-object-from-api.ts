import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

export interface ConvertObjectFromApiApiParams extends BranchContextParams {
  fieldsMapping: Record<string, any>;
}

export function convertObjectFromApi({ fieldsMapping, branchName }: ConvertObjectFromApiApiParams) {
  console.log("fieldsMapping: ", fieldsMapping);
  const mutation = gql`
    mutation {
      ConvertObjectType(
        data: {
          fields_mapping: $data
        }
      ) {
        node
      }
    }
  `;

  return graphqlClient.mutate({
    mutation,
    context: {
      branch: branchName,
    },
    variables: {
      fieldsMapping,
    },
  });
}
