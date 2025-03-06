import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { ObjectDetailsButton } from "@/shared/components/menu/object-details-button";
import { DropdownMenuItem } from "@/shared/components/ui/dropdown-menu";
import { ArtifactReGenerateButton } from "./artifact-re-generate-button";
import { ArtifactStatusBadge } from "@/entities/artifacts/ui/artifact-status-badge";
import { ArtifactStatus } from "@/entities/artifacts/types";
import { ArtifactDetailsMenu } from "@/entities/artifacts/ui/artifact-details-menu";

type ArtifactHeaderProps = {
  id: string;
  name: string;
  status: ArtifactStatus;
  hfid?: string;
  checksum?: string;
  storageId?: string;
  definitionId: string;
};

const ArtifactHeader = ({
  name,
  status,
  id,
  hfid,
  checksum,
  storageId,
  definitionId,
}: ArtifactHeaderProps) => {
  return (
    <div className="flex items-center gap-2">
      <h1 className="font-bold text-xl">{name}</h1>

      <ArtifactStatusBadge status={status} />

      <div className="flex items-center gap-1 ml-auto">
        {definitionId && (
          <ArtifactReGenerateButton
            label="Re-generate"
            artifactid={id}
            definitionid={definitionId}
          />
        )}

        <ArtifactDetailsMenu id={id} hfid={hfid} checksum={checksum} storageId={storageId} />
      </div>
    </div>
  );
};

export default ArtifactHeader;
