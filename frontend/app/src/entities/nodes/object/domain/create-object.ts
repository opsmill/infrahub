import { NodeCore } from "@/entities/nodes/types";
import {
  createObjectFromApi,
  CreateObjectFromApiApiParams,
} from "@/entities/nodes/object/api/create-object-from-api";

export type CreateObjectParams = CreateObjectFromApiApiParams;

export type CreateObject = (params: CreateObjectParams) => Promise<NodeCore>;

export const createObject: CreateObject = async (params) => {
  const { data, errors } = await createObjectFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data[`${params.objectKind}Create`].object;
};
