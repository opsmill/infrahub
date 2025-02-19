import { deleteObjectFromApi } from "@/entities/nodes/object/api/delete-object-from-api";
import { ContextParams } from "@/shared/api/types";

export type DeleteObject = (
  data: ContextParams & {
    objectKind: string;
    objectId: string;
  }
) => Promise<void>;

export const deleteObject: DeleteObject = async (data) => {
  await deleteObjectFromApi(data);
};
