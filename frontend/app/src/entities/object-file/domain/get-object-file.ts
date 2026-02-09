import type { ContextParams } from "@/shared/api/types";
import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";
import { arrayBufferToBase64, isBinaryContentType } from "@/shared/utils/file";

import { getObjectFileFromApi } from "@/entities/object-file/api/get-object-file-from-api";

export interface GetObjectFileParams extends ContextParams {
  nodeId: string;
  contentType?: string;
}

export type GetObjectFileUrlParams = Pick<GetObjectFileParams, "nodeId" | "branchName" | "atDate">;

export function getObjectFileDownloadUrl({ nodeId, branchName, atDate }: GetObjectFileUrlParams): string {
  const params = new URLSearchParams({ branch: branchName });
  if (atDate) {
    params.append("at", atDate.toISOString());
  }
  return `${INFRAHUB_API_SERVER_URL}/api/storage/files/${nodeId}?${params}`;
}

export function getObjectFileRawUrl(urlParams: GetObjectFileUrlParams): string {
  return `${getObjectFileDownloadUrl(urlParams)}&preview=true`;
}

export async function getObjectFile({
  nodeId,
  contentType,
  branchName,
  atDate,
}: GetObjectFileParams): Promise<string> {
  if (isBinaryContentType(contentType)) {
    const { data, error } = await getObjectFileFromApi({
      nodeId,
      branchName,
      atDate,
      parseAs: "arrayBuffer",
    });

    if (error) throw error;

    return arrayBufferToBase64(data as ArrayBuffer);
  }

  const { data, error } = await getObjectFileFromApi({ nodeId, branchName, atDate });

  if (error) throw error;

  return data as string;
}
