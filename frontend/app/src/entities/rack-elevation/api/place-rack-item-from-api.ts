import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

import type { RackFace } from "@/entities/rack-elevation/domain/model/rack-elevation";

const PLACE_RACK_ITEM = graphql(`
  mutation PLACE_RACK_ITEM($rackId: String!, $itemId: String!, $position: Int, $face: RackFace) {
    RackElevationPlace(rack: $rackId, item: $itemId, position: $position, face: $face) {
      ok
      item {
        id
        position
        face
        placement
      }
    }
  }
`);

export interface PlaceRackItemFromApiParams extends BranchContextParams {
  rackId: string;
  itemId: string;
  position: number | null;
  face: RackFace | null;
}

export function placeRackItemFromApi({
  rackId,
  itemId,
  position,
  face,
  branchName,
}: PlaceRackItemFromApiParams) {
  return graphqlClient.mutate({
    mutation: PLACE_RACK_ITEM,
    variables: { rackId, itemId, position, face },
    context: {
      branch: branchName,
      // The caller shows the refusal reason itself, in a toast.
      processErrorMessage: () => {},
    },
  });
}
