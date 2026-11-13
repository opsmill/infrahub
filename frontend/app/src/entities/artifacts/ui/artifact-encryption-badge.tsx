import { LockIcon } from "lucide-react";

import { Badge } from "@/shared/components/ui/badge";

import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import { useArtifactEncryptionNotice } from "@/entities/artifacts/ui/hooks/use-artifact-encryption-notice";

interface ArtifactEncryptionBadgeProps {
  artifact: ArtifactObject;
}

export function ArtifactEncryptionBadge({ artifact }: ArtifactEncryptionBadgeProps) {
  const notice = useArtifactEncryptionNotice(artifact);

  if (notice?.level !== "success") return null;

  return (
    <Badge
      variant="green"
      className="gap-1"
      title={notice.message}
      data-testid="artifact-encryption-badge"
    >
      <LockIcon className="size-3" aria-hidden="true" />
      encrypted
    </Badge>
  );
}
