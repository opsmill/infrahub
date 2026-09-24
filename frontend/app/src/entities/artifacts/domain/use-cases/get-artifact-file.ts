import type { RestErrorItem } from "@/shared/api/rest/fetch";
import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";
import { arrayBufferToBase64, isBinaryContentType } from "@/shared/utils/file";

import { getArtifactFileFromApi } from "@/entities/artifacts/api/get-artifact-file-from-api";

export interface GetArtifactFileParams {
  storageId: string;
  contentType?: string;
}

const DEFAULT_ERROR_MESSAGE = "Unable to load the artifact file";

export function getArtifactFileDownloadUrl(storageId: string): string {
  return `${INFRAHUB_API_SERVER_URL}/api/storage/object/${storageId}`;
}

// The REST envelope carries the reason in `errors[0].message`, which the UI shows as is: an artifact
// refused for failing its integrity check must say so rather than look empty.
function toArtifactFileError(error: unknown): Error {
  const message = (error as { errors?: RestErrorItem[] } | undefined)?.errors?.[0]?.message;
  return new Error(message || DEFAULT_ERROR_MESSAGE);
}

export async function getArtifactFile({
  storageId,
  contentType,
}: GetArtifactFileParams): Promise<string> {
  if (isBinaryContentType(contentType)) {
    const { data, error } = await getArtifactFileFromApi({ storageId, parseAs: "arrayBuffer" });

    if (error) throw toArtifactFileError(error);

    return arrayBufferToBase64(data as ArrayBuffer);
  }

  const { data, error } = await getArtifactFileFromApi({ storageId });

  if (error) throw toArtifactFileError(error);

  return data as string;
}
