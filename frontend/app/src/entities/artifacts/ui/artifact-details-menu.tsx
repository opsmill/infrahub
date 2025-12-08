import { CopyToClipboardMenuItem } from "@/shared/components/aria/menu";
import { ARTIFACT_OBJECT } from "@/shared/config/constants";

import {
  ObjectDetailsButton,
  type ObjectDetailsButtonProps,
} from "@/entities/nodes/object/ui/object-details-button";

export interface ArtifactDetailsMenuProps extends ObjectDetailsButtonProps {
  checksum?: string;
  storageId?: string;
}

export function ArtifactDetailsMenu({ id, hfid, checksum, storageId }: ArtifactDetailsMenuProps) {
  return (
    <ObjectDetailsButton id={id} hfid={hfid} objectKind={ARTIFACT_OBJECT}>
      {checksum && (
        <CopyToClipboardMenuItem textToCopy={checksum}>Copy Checksum</CopyToClipboardMenuItem>
      )}

      {storageId && (
        <CopyToClipboardMenuItem textToCopy={storageId}>Copy Storage ID</CopyToClipboardMenuItem>
      )}
    </ObjectDetailsButton>
  );
}
