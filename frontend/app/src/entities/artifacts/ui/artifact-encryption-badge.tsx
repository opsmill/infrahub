import { LockIcon } from "lucide-react";

import { Badge } from "@/shared/components/ui/badge";

import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import { useArtifactContentState } from "@/entities/artifacts/ui/hooks/use-artifact-content-state";
import { useArtifactEncryptionState } from "@/entities/artifacts/ui/hooks/use-artifact-encryption-state";

interface ArtifactEncryptionBadgeProps {
  artifact: ArtifactObject;
}

export function ArtifactEncryptionBadge({ artifact }: ArtifactEncryptionBadgeProps) {
  const encryption = useArtifactEncryptionState(artifact);
  const { isSettled, isNotServed } = useArtifactContentState(artifact);

  // The check reads only the file header, so a file whose content was changed passes it until the content is refused.
  if (encryption?.state !== "encrypted" || !isSettled || isNotServed) return null;

  return (
    <Badge
      variant="green"
      className="gap-1"
      title="This artifact is encrypted."
      data-testid="artifact-encryption-badge"
    >
      <LockIcon className="size-3" aria-hidden="true" />
      encrypted
    </Badge>
  );
}
