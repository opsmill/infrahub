import {
  type GetObjectFileFromApiParams,
  getObjectFileFromApi,
} from "@/entities/object-file/api/get-object-file-from-api";

export type GetObjectFileParams = GetObjectFileFromApiParams;

export async function getObjectFile({ nodeId }: GetObjectFileParams): Promise<string> {
  if (!nodeId) {
    throw new Error("Node ID is required to fetch object file");
  }

  const { data, error } = await getObjectFileFromApi({ nodeId });

  if (error) throw error;

  return data;
}
