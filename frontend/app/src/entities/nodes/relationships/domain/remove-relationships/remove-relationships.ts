import type { BranchContextParams } from "@/shared/api/types";

import { removeRelationshipsFromApi } from "@/entities/nodes/relationships/api/remove-relationships-from-api";

export type RemoveRelationshipsParams = BranchContextParams & {
  objectId: string;
  relationshipName: string;
  relationshipIds: Array<string>;
};

export type RemoveRelationships = (params: RemoveRelationshipsParams) => Promise<void>;

export const removeRelationships: RemoveRelationships = async ({
  objectId,
  relationshipName,
  relationshipIds,
  branchName,
}) => {
  await removeRelationshipsFromApi({
    objectId,
    relationshipName,
    relationshipIds: relationshipIds.map((id) => ({ id })),
    branchName,
  });
};
