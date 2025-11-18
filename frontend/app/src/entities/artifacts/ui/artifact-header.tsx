import type { ArtifactStatus } from "@/entities/artifacts/types";
import { ArtifactDetailsMenu } from "@/entities/artifacts/ui/artifact-details-menu";
import { ArtifactStatusBadge } from "@/entities/artifacts/ui/artifact-status-badge";

import { ArtifactGenerateButton } from "./artifact-generate-button";

type ArtifactHeaderProps = {
  id: string;
  name: string;
  status: ArtifactStatus;
  hfid?: string;
  checksum?: string;
  storageId?: string;
  artifactDefinitionId: string;
};

const ArtifactHeader = ({
  name,
  status,
  id,
  hfid,
  checksum,
  storageId,
  artifactDefinitionId,
}: ArtifactHeaderProps) => {
  return (
    <div className="flex items-center gap-2">
      <h1 className="font-bold text-xl">{name}</h1>

      <ArtifactStatusBadge status={status} />

      <div className="ml-auto flex items-center gap-1">
        {artifactDefinitionId && (
          <ArtifactGenerateButton
            label="Re-generate"
            artifactId={id}
            artifactDefinitionId={artifactDefinitionId}
          />
        )}

        <ArtifactDetailsMenu id={id} hfid={hfid} checksum={checksum} storageId={storageId} />
      </div>
    </div>
  );
};

export default ArtifactHeader;
