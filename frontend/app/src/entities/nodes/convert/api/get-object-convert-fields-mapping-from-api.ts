import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

const GET_FIELDS_MAPPING = graphql(`
  query ($sourceKind: String, $targetKind: String) {
    FieldsMappingTypeConversion(source_kind: $sourceKind, target_kind: $targetKind) {
      mapping
    }
  }
`);

type QueryVariables = VariablesOf<typeof GET_FIELDS_MAPPING>;

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
    query: GET_FIELDS_MAPPING,
    variables: {
      sourceKind,
      targetKind,
    } satisfies QueryVariables,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
