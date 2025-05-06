import { deleteObjectsFromApi } from "@/entities/nodes/object/api/delete-objects-from-api";
import { DeleteObjectsParams } from "@/entities/nodes/object/api/delete-objects-from-api";
import { ContextParams } from "@/shared/api/types";

export type DeleteObject = (data: ContextParams & DeleteObjectsParams) => Promise<void>;

export const deleteObjects: DeleteObject = async (data) => {
  await deleteObjectsFromApi(data);
};
