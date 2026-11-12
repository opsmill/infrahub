import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const GET_RACK_ELEVATION_KINDS = graphql(`
  query GET_RACK_ELEVATION_KINDS {
    RackElevationKinds {
      kind
      role
    }
  }
`);

export type GetRackElevationKindsFromApiParams = ContextParams;

export function getRackElevationKindsFromApi({
  branchName,
  atDate,
}: GetRackElevationKindsFromApiParams) {
  return graphqlClient.query({
    query: GET_RACK_ELEVATION_KINDS,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
