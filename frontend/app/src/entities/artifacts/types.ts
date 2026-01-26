import type { CoreArtifact } from "@/shared/api/graphql/generated/graphql";

import type { NodeCore } from "@/entities/nodes/types";

export type ArtifactStatus = "Error" | "Pending" | "Processing" | "Ready";

export type ArtifactContentType =
  | "application/json"
  | "application/yaml"
  | "application/hcl"
  | "application/graphql"
  | "image/svg+xml"
  | "text/plain"
  | "text/markdown"
  | "application/xml"
  | "text/csv";

export interface ArtifactObject extends NodeCore {
  checksum: NonNullable<CoreArtifact["checksum"]> & { value: string };
  content_type: NonNullable<CoreArtifact["content_type"]> & { value: ArtifactContentType };
  storage_id: NonNullable<CoreArtifact["storage_id"]> & { value: string };
  status: NonNullable<CoreArtifact["status"]> & { value: ArtifactStatus };
  definition: NonNullable<CoreArtifact["definition"]> & { node: NodeCore };
  object: NonNullable<CoreArtifact["object"]> & { node: NodeCore };
}

export function assertArtifactObject(data: NodeCore | null | undefined): ArtifactObject | null {
  const artifact = data as Partial<ArtifactObject> | null | undefined;

  if (
    !artifact?.content_type?.value ||
    !artifact.storage_id?.value ||
    !artifact.status?.value ||
    !artifact.checksum?.value ||
    !artifact.definition?.node ||
    !artifact.object?.node
  ) {
    return null;
  }

  return artifact as ArtifactObject;
}
