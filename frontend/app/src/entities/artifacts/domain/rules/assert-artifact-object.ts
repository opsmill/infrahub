import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";

export function assertArtifactObject(data: NodeCore | null | undefined): ArtifactObject | null {
  const artifact = data as Partial<ArtifactObject> | null | undefined;

  if (
    !artifact?.content_type?.value ||
    !artifact.status?.value ||
    !artifact.definition?.node ||
    !artifact.object?.node
  ) {
    return null;
  }

  return artifact as ArtifactObject;
}
