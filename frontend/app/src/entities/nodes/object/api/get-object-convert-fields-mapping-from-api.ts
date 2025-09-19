import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

const query = gql`
  query($sourceKind: String, $targetKind: String) {
    FieldsMappingTypeConversion(source_kind: $sourceKind, target_kind: $targetKind) {
      mapping
    }
  }
`;

export interface GetObjectConvertFieldsMappingFromApiParams extends ContextParams {
  sourceKind: string;
  targetKind: string;
}

export function getObjectConvertFieldsMappingFromApi({
  sourceKind,
  targetKind,
  branchName,
  atDate,
}: GetObjectConvertFieldsMappingFromApiParams) {
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
