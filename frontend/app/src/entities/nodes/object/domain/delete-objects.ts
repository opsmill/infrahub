import { deleteObjectsFromApi } from "@/entities/nodes/object/api/delete-objects-from-api";
import { ContextParams } from "@/shared/api/types";

export type DeleteObject = (
  data: ContextParams & {
    objectKind: string;
    objectIds: Array<string>;
  }
) => Promise<void>;

export const deleteObjects: DeleteObject = async (data) => {
  await deleteObjectsFromApi(data);
};
