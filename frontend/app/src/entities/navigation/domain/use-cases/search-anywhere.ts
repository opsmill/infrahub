import {
  type SearchAnywhereFromApiParams,
  searchAnywhereFromApi,
} from "@/entities/navigation/api/search-from-api";

export type SearchAnywhereParams = SearchAnywhereFromApiParams;

export type ObjectResult = { id: string; kind: string };

export type SearchAnywhereResult = {
  matchingObjects: Array<ObjectResult>;
  hasMore: boolean;
  parentPrefixes: Array<ObjectResult> | null;
};

export type SearchAnywhere = (params: SearchAnywhereParams) => Promise<SearchAnywhereResult>;

export const searchAnywhere: SearchAnywhere = async (params) => {
  // One row past the limit tells whether more matches exist, without counting them all.
  const { data, errors } = await searchAnywhereFromApi({ ...params, limit: params.limit + 1 });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const { InfrahubSearchAnywhere } = data;
  const matchingObjects = InfrahubSearchAnywhere.edges?.map(({ node }) => node) ?? [];

  return {
    matchingObjects: matchingObjects.slice(0, params.limit),
    hasMore: matchingObjects.length > params.limit,
    parentPrefixes: InfrahubSearchAnywhere.parent_prefixes?.map(({ node }) => node) ?? null,
  };
};
