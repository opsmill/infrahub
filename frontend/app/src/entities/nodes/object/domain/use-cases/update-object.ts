import {
  type UpdateObjectFromApiParams,
  updateObjectFromApi,
} from "@/entities/nodes/object/api/update-object-from-api";
import type { NodeCore } from "@/entities/nodes/types";

export type UpdateObjectParams = UpdateObjectFromApiParams;

export type UpdateObject = (params: UpdateObjectParams) => Promise<NodeCore>;

export const updateObject: UpdateObject = async (params) => {
  const { data, errors } = await updateObjectFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data[`${params.objectKind}Update`].object;
};
