import React from "react";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { warnUnexpectedType } from "@/shared/utils/common";

import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import type { ArtifactUnreadableReason } from "@/entities/artifacts/domain/rules/get-artifact-encryption-state";
import { useArtifactEncryptionState } from "@/entities/artifacts/ui/hooks/use-artifact-encryption-state";

const UNREADABLE_REASON_MESSAGES: Record<ArtifactUnreadableReason, string> = {
  unknown_key: "It was not encrypted with the current key.",
  no_key: "No encryption key is configured.",
  unsupported_format: "The file is in a format this version cannot read.",
  truncated: "The file is incomplete.",
};

interface ArtifactEncryptionNoticeProps {
  artifact: ArtifactObject;
}

export function ArtifactEncryptionNotice({ artifact }: ArtifactEncryptionNoticeProps) {
  const encryption = useArtifactEncryptionState(artifact);

  if (!encryption) return null;

  switch (encryption.state) {
    case "plaintext":
      return (
        <DismissibleAlert type={ALERT_TYPES.WARNING}>
          This artifact is stored without encryption. Encryption only applies to artifacts stored
          after it was enabled.
        </DismissibleAlert>
      );
    case "unreadable":
      return (
        <DismissibleAlert type={ALERT_TYPES.ERROR}>
          This artifact is encrypted but cannot be read with the current encryption key.
          {encryption.reason && ` ${UNREADABLE_REASON_MESSAGES[encryption.reason]}`}
        </DismissibleAlert>
      );
    case "missing":
      return (
        <DismissibleAlert type={ALERT_TYPES.ERROR}>
          The file of this artifact is missing from the storage.
        </DismissibleAlert>
      );
    case "encrypted":
      // A confirmed encryption needs no action from the user, so it is a badge in the header and not a notice.
      return null;
    default:
      warnUnexpectedType(encryption);
      return null;
  }
}

interface DismissibleAlertProps {
  type: ALERT_TYPES;
  children: React.ReactNode;
}

function DismissibleAlert({ type, children }: DismissibleAlertProps) {
  const [isDismissed, setIsDismissed] = React.useState(false);

  if (isDismissed) return null;

  return (
    <div data-testid="artifact-encryption-notice">
      <Alert type={type} message={children} onDismiss={() => setIsDismissed(true)} />
    </div>
  );
}
