import { getObjectsCountFromApi } from "@/entities/nodes/object/api/get-objects-count-from-api";
import { ContextParams } from "@/shared/api/types";
import { Filter } from "@/shared/hooks/useFilters";

export type GetObjectsCountParams = ContextParams & {
  schemaKind: string;
  filters?: Array<Filter>;
};

export type GetObjectsCount = (args: GetObjectsCountParams) => Promise<number>;

export const getObjectsCount: GetObjectsCount = async ({
  schemaKind,
  branchName,
  atDate,
  filters = [],
}) => {
  const kindFilter = filters?.find((filter) => filter.name === "kind__value");
  const schemaKindToQuery: string = kindFilter?.value ?? schemaKind;

  const { data } = await getObjectsCountFromApi({
    schemaKind: schemaKindToQuery,
    branchName,
    atDate,
  });

  return data[schemaKindToQuery].count;
};
