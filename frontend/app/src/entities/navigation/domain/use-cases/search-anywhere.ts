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

export const searchAnywhere: SearchAnywhere = async ({ limit, ...params }) => {
  // Fetch one more row than the limit, without displaying it, to know whether more results exist.
  const { data, errors } = await searchAnywhereFromApi({ ...params, limit: limit + 1 });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const { InfrahubSearchAnywhere } = data;
  const objects = InfrahubSearchAnywhere.edges?.map(({ node }) => node) ?? [];

  return {
    matchingObjects: objects.slice(0, limit),
    hasMore: objects.length > limit,
    parentPrefixes: InfrahubSearchAnywhere.parent_prefixes?.map(({ node }) => node) ?? null,
  };
};
