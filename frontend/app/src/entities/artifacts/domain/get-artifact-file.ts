import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";
import { arrayBufferToBase64, isBinaryContentType } from "@/shared/utils/file";

import { getArtifactFileFromApi } from "@/entities/artifacts/api/get-artifact-file-from-api";

export interface GetArtifactFileParams {
  storageId: string;
  contentType?: string;
}

export function getArtifactFileDownloadUrl(storageId: string): string {
  return `${INFRAHUB_API_SERVER_URL}/api/storage/object/${storageId}`;
}

export async function getArtifactFile({
  storageId,
  contentType,
}: GetArtifactFileParams): Promise<string> {
  if (isBinaryContentType(contentType)) {
    const { data, error } = await getArtifactFileFromApi({ storageId, parseAs: "arrayBuffer" });

    if (error) throw error;

    return arrayBufferToBase64(data as ArrayBuffer);
  }

  const { data, error } = await getArtifactFileFromApi({ storageId });

  if (error) throw error;

  return data as string;
}
