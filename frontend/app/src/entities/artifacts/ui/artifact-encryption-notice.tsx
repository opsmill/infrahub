import { useState } from "react";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import { useArtifactEncryptionNotice } from "@/entities/artifacts/ui/hooks/use-artifact-encryption-notice";

const ALERT_TYPES_BY_LEVEL = {
  warning: ALERT_TYPES.WARNING,
  error: ALERT_TYPES.ERROR,
} as const;

interface ArtifactEncryptionNoticeProps {
  artifact: ArtifactObject;
}

export function ArtifactEncryptionNotice({ artifact }: ArtifactEncryptionNoticeProps) {
  const [isDismissed, setIsDismissed] = useState(false);
  const notice = useArtifactEncryptionNotice(artifact);

  // A confirmed encryption needs no action from the user, so it is a badge in the header and not a notice.
  if (!notice || notice.level === "success" || isDismissed) return null;

  return (
    <div data-testid="artifact-encryption-notice">
      <Alert
        type={ALERT_TYPES_BY_LEVEL[notice.level]}
        message={notice.message}
        onDismiss={() => setIsDismissed(true)}
      />
    </div>
  );
}
