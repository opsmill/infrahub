import { CONFIG } from "@/shared/config/config";
import { arrayBufferToBase64, isBinaryContentType } from "@/shared/utils/file";

import { getObjectFileFromApi } from "@/entities/object-file/api/get-object-file-from-api";

export interface GetObjectFileParams {
  nodeId: string;
  contentType?: string;
}

export function getObjectFileDownloadUrl(nodeId: string): string {
  return CONFIG.FILE_BY_NODE_ID_URL(nodeId);
}

export function getObjectFileRawUrl(nodeId: string): string {
  return CONFIG.FILE_BY_NODE_ID_URL(nodeId, true);
}

export async function getObjectFile({ nodeId, contentType }: GetObjectFileParams): Promise<string> {
  if (!nodeId) {
    throw new Error("Node ID is required to fetch object file");
  }

  if (isBinaryContentType(contentType)) {
    const { data, error } = await getObjectFileFromApi({ nodeId, parseAs: "arrayBuffer" });

    if (error) throw error;

    return arrayBufferToBase64(data as ArrayBuffer);
  }

  const { data, error } = await getObjectFileFromApi({ nodeId });

  if (error) throw error;

  return data as string;
}
