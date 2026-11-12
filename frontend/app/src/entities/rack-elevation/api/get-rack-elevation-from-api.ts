import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const GET_RACK_ELEVATION = graphql(`
  query GET_RACK_ELEVATION($rackId: String!, $labelBy: String, $colorBy: String) {
    RackElevation(rack: $rackId, label_by: $labelBy, color_by: $colorBy) {
      rack {
        id
        kind
        display_label
        u_height
        used_units
        utilization
        total_weight
      }
      items {
        id
        kind
        display_label
        label
        color
        placement
        position
        face
        u_height
        full_depth
        weight
        type_id
        type_display_label
      }
    }
  }
`);

export interface GetRackElevationFromApiParams extends ContextParams {
  rackId: string;
  labelBy?: string | null;
  colorBy?: string | null;
}

export function getRackElevationFromApi({
  rackId,
  labelBy,
  colorBy,
  branchName,
  atDate,
}: GetRackElevationFromApiParams) {
  return graphqlClient.query({
    query: GET_RACK_ELEVATION,
    variables: { rackId, labelBy, colorBy },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
