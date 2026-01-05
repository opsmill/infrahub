import {
  type DeleteObjectsFromApiParams,
  deleteObjectsFromApi,
} from "@/entities/nodes/object/api/delete-objects-from-api";

export type DeleteObject = (data: DeleteObjectsFromApiParams) => Promise<void>;

export const deleteObjects: DeleteObject = async (data) => {
  await deleteObjectsFromApi(data);
};
