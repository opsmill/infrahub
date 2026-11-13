import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import {
  type ArtifactEncryptionNotice,
  getArtifactEncryptionNotice,
} from "@/entities/artifacts/domain/rules/get-artifact-encryption-notice";
import { useCheckArtifactEncryption } from "@/entities/artifacts/ui/queries/check-artifact-encryption.query";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";

export function useArtifactEncryptionNotice(
  artifact: ArtifactObject
): ArtifactEncryptionNotice | null {
  const { data: appInfo } = useGetAppInfo();
  const { data: check } = useCheckArtifactEncryption(artifact.id);
  const timeMachineDate = useAtomValue(datetimeAtom);

  // A check describes the file and the key as they are now, so a past date only has the value stored at that date.
  const currentCheck = timeMachineDate === null ? check : undefined;

  return getArtifactEncryptionNotice({
    encryption: currentCheck?.encryption ?? artifact.encryption?.value,
    reason: currentCheck?.reason,
    isEncryptionEnabled: appInfo?.storage_encryption_enabled ?? false,
    isVerified: currentCheck !== undefined && currentCheck.reason !== "missing",
  });
}
