import {
  GetObjectsCountFromApiParams,
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
  const kindFilter = filters?.find((filter) => filter.name === "kind__value");
  const schemaKindToQuery: string = kindFilter?.value ?? objectKind;

  const { data, errors } = await getObjectsCountFromApi({
    objectKind: schemaKindToQuery,
    branchName,
    atDate,
    filters,
  });

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data[schemaKindToQuery].count;
};
