import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

export interface ConvertFieldsMappingParams extends ContextParams {
  sourceKind?: string;
  targetKind: string;
}

const query = gql`
query($sourceKind: String, $targetKind: String) {
  FieldsMappingTypeConversion(source_kind: $sourceKind, target_kind: $targetKind) {
    mapping
  }
}
`;

export function getConvertFieldsMappingFromApi({
  sourceKind,
  targetKind,
  branchName,
  atDate,
}: ConvertFieldsMappingParams) {
  return graphqlClient.query({
    query,
    variables: {
      sourceKind,
      targetKind,
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
