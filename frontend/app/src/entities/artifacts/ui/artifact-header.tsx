import type { ArtifactObject } from "@/entities/artifacts/types";
import { ArtifactDetailsMenu } from "@/entities/artifacts/ui/artifact-details-menu";
import { ArtifactGenerateButton } from "@/entities/artifacts/ui/artifact-generate-button";
import { ArtifactStatusBadge } from "@/entities/artifacts/ui/artifact-status-badge";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/object-details/node-metadata-popover";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";

interface ArtifactHeaderProps {
  artifact: ArtifactObject;
}

export function ArtifactHeader({ artifact }: ArtifactHeaderProps) {
  return (
    <div className="flex items-center gap-2">
      <h1 className="font-bold text-xl">{getNodeLabel(artifact)}</h1>
      <NodeMetadataPopover objectKind={artifact.__typename} objectId={artifact.id} />
      <ArtifactStatusBadge status={artifact.status.value} />

      <div className="ml-auto flex items-center gap-1">
        <ArtifactGenerateButton
          label="Re-generate"
          artifactId={artifact.id}
          artifactDefinitionId={artifact.definition.node.id}
        />

        <ArtifactDetailsMenu artifact={artifact} />
      </div>
    </div>
  );
}
