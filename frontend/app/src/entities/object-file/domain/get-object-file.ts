import type { ContextParams } from "@/shared/api/types";
import { CONFIG } from "@/shared/config/config";
import { arrayBufferToBase64, isBinaryContentType } from "@/shared/utils/file";

import { getObjectFileFromApi } from "@/entities/object-file/api/get-object-file-from-api";

export interface GetObjectFileParams extends ContextParams {
  nodeId: string;
  contentType?: string;
}

export function getObjectFileDownloadUrl(nodeId: string, branchName: string): string {
  return CONFIG.FILE_BY_NODE_ID_URL(nodeId, branchName);
}

export function getObjectFileRawUrl(nodeId: string, branchName: string): string {
  return CONFIG.FILE_BY_NODE_ID_URL(nodeId, branchName, true);
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
