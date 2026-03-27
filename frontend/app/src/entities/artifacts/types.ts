import type { DataViewerContentType } from "@/shared/components/data-viewer/types";

import type { NodeCore } from "@/entities/nodes/types";

export type ArtifactStatus = "Error" | "Pending" | "Processing" | "Ready";

export interface ArtifactObject extends NodeCore {
  checksum: { value: string | null };
  content_type: { value: DataViewerContentType };
  storage_id: { value: string | null };
  status: { value: ArtifactStatus };
  definition: { node: NodeCore };
  object: { node: NodeCore };
}

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
