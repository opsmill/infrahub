import {
  type ConvertObjectFromApiApiParams,
  convertObjectFromApi,
} from "@/entities/nodes/convert/api/convert-object-from-api";
import type { NodeCore } from "@/entities/nodes/types";

export type ConvertObjectParams = ConvertObjectFromApiApiParams;

export type ConvertObject = (params: ConvertObjectParams) => Promise<NodeCore>;

export const convertObject: ConvertObject = async (params) => {
  const { data, errors } = await convertObjectFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data.ConvertObjectType.node;
};
