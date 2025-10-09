import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

export interface ConvertObjectFromApiApiParams extends BranchContextParams {
  nodeId: string;
  targetKind: string;
  fieldsMapping: Record<string, any>;
}

export function convertObjectFromApi({
  fieldsMapping,
  nodeId,
  targetKind,
  branchName,
}: ConvertObjectFromApiApiParams) {
  const mutation = gql`
    mutation ($nodeId: String!, $targetKind: String!, $fieldsMapping: GenericScalar!) {
      ConvertObjectType(
        data: {
          node_id: $nodeId
          target_kind: $targetKind
          fields_mapping: $fieldsMapping
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
      processErrorMessage: () => {},
    },
    variables: {
      nodeId,
      targetKind,
      fieldsMapping,
    },
  });
}
