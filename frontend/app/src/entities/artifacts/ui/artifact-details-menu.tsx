import { CopyToClipboardMenuItem } from "@/shared/components/aria/menu";
import { ARTIFACT_OBJECT } from "@/shared/config/constants";

import type { ArtifactObject } from "@/entities/artifacts/types";
import { ObjectDetailsButton } from "@/entities/nodes/object/ui/object-details-button";

export interface ArtifactDetailsMenuProps {
  artifact: ArtifactObject;
}

export function ArtifactDetailsMenu({ artifact }: ArtifactDetailsMenuProps) {
  return (
    <ObjectDetailsButton
      id={artifact.id}
      hfid={artifact.hfid?.toString()}
      objectKind={ARTIFACT_OBJECT}
    >
      <CopyToClipboardMenuItem textToCopy={artifact.checksum.value}>
        Copy Checksum
      </CopyToClipboardMenuItem>

      <CopyToClipboardMenuItem textToCopy={artifact.storage_id.value}>
        Copy Storage ID
      </CopyToClipboardMenuItem>
    </ObjectDetailsButton>
  );
}
