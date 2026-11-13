import { useAtomValue } from "jotai";
import { LockIcon } from "lucide-react";
import { useState } from "react";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { datetimeAtom } from "@/shared/stores/time.atom";

import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import { getArtifactEncryptionNotice } from "@/entities/artifacts/domain/rules/get-artifact-encryption-notice";
import { useCheckArtifactEncryption } from "@/entities/artifacts/ui/queries/check-artifact-encryption.query";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";

const ALERT_TYPES_BY_LEVEL = {
  success: ALERT_TYPES.SUCCESS,
  warning: ALERT_TYPES.WARNING,
  error: ALERT_TYPES.ERROR,
} as const;

interface ArtifactEncryptionNoticeProps {
  artifact: ArtifactObject;
}

export function ArtifactEncryptionNotice({ artifact }: ArtifactEncryptionNoticeProps) {
  const [isDismissed, setIsDismissed] = useState(false);
  const { data: appInfo } = useGetAppInfo();
  const { data: check } = useCheckArtifactEncryption(artifact.id);
  const timeMachineDate = useAtomValue(datetimeAtom);

  // The notice describes the file and the key as they are now, so it says nothing about a past date.
  if (timeMachineDate !== null) return null;

  // The check reads the file now; the stored value is what the artifact held when it was fetched.
  const notice = getArtifactEncryptionNotice({
    encryption: check?.encryption ?? artifact.encryption?.value,
    reason: check?.reason,
    isEncryptionEnabled: appInfo?.storage_encryption_enabled ?? false,
    isVerified: check !== undefined && check.reason !== "missing",
  });

  if (!notice || isDismissed) return null;

  return (
    <div data-testid="artifact-encryption-notice">
      <Alert
        type={ALERT_TYPES_BY_LEVEL[notice.level]}
        icon={
          notice.level === "success" ? (
            <LockIcon className="h-4 w-4 text-green-500" aria-hidden="true" />
          ) : undefined
        }
        message={notice.message}
        onDismiss={() => setIsDismissed(true)}
      />
    </div>
  );
}
