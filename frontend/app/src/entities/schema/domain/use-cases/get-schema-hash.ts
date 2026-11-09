import {
  type GetSchemaSummaryFromApiParams,
  getSchemaSummaryFromApi,
} from "@/entities/schema/api/get-schema-summary-from-api";

export type GetSchemaHashParams = GetSchemaSummaryFromApiParams;

export type GetSchemaHash = (params: GetSchemaHashParams) => Promise<string>;

export const getSchemaHash: GetSchemaHash = async ({ branchName, atDate }) => {
  const { data, error } = await getSchemaSummaryFromApi({ branchName, atDate });

  if (error) throw error;

  return data.main;
};
