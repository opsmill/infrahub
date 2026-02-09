import { CONFIG } from "@/shared/config/config";
import { arrayBufferToBase64, isBinaryContentType } from "@/shared/utils/file";

import { getObjectFileFromApi } from "@/entities/object-file/api/get-object-file-from-api";

export interface GetObjectFileParams {
  nodeId: string;
  contentType?: string;
  branch: string;
}

export function getObjectFileDownloadUrl(nodeId: string, branch: string): string {
  return CONFIG.FILE_BY_NODE_ID_URL(nodeId, branch);
}

export function getObjectFileRawUrl(nodeId: string, branch: string): string {
  return CONFIG.FILE_BY_NODE_ID_URL(nodeId, branch, true);
}

export async function getObjectFile({
  nodeId,
  contentType,
  branch,
}: GetObjectFileParams): Promise<string> {
  if (isBinaryContentType(contentType)) {
    const { data, error } = await getObjectFileFromApi({ nodeId, branch, parseAs: "arrayBuffer" });

    if (error) throw error;

    return arrayBufferToBase64(data as ArrayBuffer);
  }

  const { data, error } = await getObjectFileFromApi({ nodeId, branch });

  if (error) throw error;

  return data as string;
}
