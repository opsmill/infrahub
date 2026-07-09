import {
  type GetObjectsCountFromApiParams,
  getObjectsCountFromApi,
} from "@/entities/nodes/object/api/get-objects-count-from-api";

export type GetObjectsCountParams = GetObjectsCountFromApiParams;

export type GetObjectsCount = (args: GetObjectsCountParams) => Promise<number>;

export const getObjectsCount: GetObjectsCount = async ({
  objectKind,
  branchName,
  atDate,
  filters = [],
}) => {
  const { data, errors } = await getObjectsCountFromApi({
    objectKind,
    branchName,
    atDate,
    filters,
  });

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data[objectKind].count;
};
