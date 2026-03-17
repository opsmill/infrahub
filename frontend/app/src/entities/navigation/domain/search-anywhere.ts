import {
  type SearchAnywhereFromApiParams,
  searchAnywhereFromApi,
} from "@/entities/navigation/api/search";

export type SearchAnywhereParams = SearchAnywhereFromApiParams;

export type ObjectResult = { id: string; kind: string };

export type SearchAnywhereResult = {
  count: number;
  matchingObjects: Array<ObjectResult>;
  parentPrefixes: Array<ObjectResult> | null;
};

export type SearchAnywhere = (params: SearchAnywhereParams) => Promise<SearchAnywhereResult>;

export const searchAnywhere: SearchAnywhere = async (params) => {
  const { data, errors } = await searchAnywhereFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const { InfrahubSearchAnywhere } = data;

  return {
    count: InfrahubSearchAnywhere.count,
    matchingObjects: InfrahubSearchAnywhere.edges?.map(({ node }) => node) ?? [],
    parentPrefixes:
      InfrahubSearchAnywhere.parent_prefixes?.map(({ node }) => node) ?? null,
  };
};
