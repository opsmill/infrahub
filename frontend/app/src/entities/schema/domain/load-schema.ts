import {
  type GetSchemaFromApiParams,
  getSchemaFromApi,
} from "@/entities/schema/api/get-schema-from-api";

export type LoadSchemaParams = GetSchemaFromApiParams;

export const loadSchema = async ({ branchName, atDate }: LoadSchemaParams) => {
  const { data, error } = await getSchemaFromApi({ branchName, atDate });

  if (error) throw error;

  return data;
};
