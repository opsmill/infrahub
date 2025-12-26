import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

const CONVERT_OBJECT_MUTATION = graphql(`
  mutation ($nodeId: String!, $targetKind: String!, $fieldsMapping: GenericScalar!) {
    ConvertObjectType(
      data: { node_id: $nodeId, target_kind: $targetKind, fields_mapping: $fieldsMapping }
    ) {
      node
    }
  }
`);

type MutationVariables = VariablesOf<typeof CONVERT_OBJECT_MUTATION>;

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
  return graphqlClient.mutate({
    mutation: CONVERT_OBJECT_MUTATION,
    context: {
      branch: branchName,
      processErrorMessage: () => {},
    },
    variables: {
      nodeId,
      targetKind,
      fieldsMapping,
    } satisfies MutationVariables,
  });
}
