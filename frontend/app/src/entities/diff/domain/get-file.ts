import { type GetFileFromApiParams, getFileFromApi } from "@/entities/diff/api/get-file-from-api";

export type GetFileParams = GetFileFromApiParams;

export async function getFile(params: GetFileParams): Promise<string | null> {
  const { data, error, response } = await getFileFromApi(params);

  // 404 means file doesn't exist at this commit (new or deleted file)
  if (response.status === 404) {
    return null;
  }

  if (error) throw error;

  return data ?? "";
}
