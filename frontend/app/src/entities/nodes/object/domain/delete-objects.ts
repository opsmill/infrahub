import { deleteObjectsFromApi } from "@/entities/nodes/object/api/delete-objects-from-api";
import { DeleteObjectsParams } from "@/entities/nodes/object/api/delete-objects-from-api";
import { ContextParams } from "@/shared/api/types";
import { DefaultContext } from "@apollo/client";

export type DeleteObject = (
  data: ContextParams & DeleteObjectsParams & DefaultContext
) => Promise<void>;

export const deleteObjects: DeleteObject = async (data) => {
  await deleteObjectsFromApi(data);
};
