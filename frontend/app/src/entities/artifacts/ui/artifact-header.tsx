import { RefreshButton } from "@/shared/components/buttons/refresh-button";

import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import { ArtifactDetailsMenu } from "@/entities/artifacts/ui/artifact-details-menu";
import { ArtifactGenerateButton } from "@/entities/artifacts/ui/artifact-generate-button";
import { ArtifactStatusBadge } from "@/entities/artifacts/ui/artifact-status-badge";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/metadata/node-metadata-popover";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

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
        <RefreshButton queryKeys={[objectQueryKeys.all]} />

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
