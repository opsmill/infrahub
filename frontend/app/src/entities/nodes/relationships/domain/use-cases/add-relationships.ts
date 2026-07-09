import {
  type AddRelationshipsToApiParams,
  addRelationshipsToApi,
} from "@/entities/nodes/relationships/api/add-relationships-from-api";

export type AddRelationshipsParams = Omit<AddRelationshipsToApiParams, "relationshipIds"> & {
  relationshipIds: Array<string | { from_pool: { id: string } }>;
};

export type AddRelationships = (params: AddRelationshipsParams) => Promise<void>;

export const addRelationships: AddRelationships = async ({
  objectId,
  relationshipName,
  relationshipIds,
  branchName,
}) => {
  await addRelationshipsToApi({
    objectId,
    relationshipName,
    relationshipIds: relationshipIds.map((entry) =>
      typeof entry === "string" ? { id: entry } : { from_pool: entry.from_pool }
    ),
    branchName,
  });
};
