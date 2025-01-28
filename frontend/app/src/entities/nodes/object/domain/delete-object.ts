import { deleteObjectFromApi } from "@/entities/nodes/object/api/delete-object-from-api";

export type DeleteObject = (data: {
  objectKind: string;
  objectId: string;
  branchName: string;
  atDate: Date | null;
}) => Promise<void>;

export const deleteObject: DeleteObject = async (data) => {
  await deleteObjectFromApi(data);
};
