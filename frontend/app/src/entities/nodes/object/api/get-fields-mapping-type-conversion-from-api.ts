import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";

interface FieldsMappingParams extends ContextParams {
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

export function getFieldsMappingFromApi({
  sourceKind,
  targetKind,
  branchName,
  atDate,
}: FieldsMappingParams) {
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
