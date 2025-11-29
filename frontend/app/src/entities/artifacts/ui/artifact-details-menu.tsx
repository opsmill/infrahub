import { CopyToClipboardMenuItem } from "@/shared/components/aria/menu";
import {
  ObjectDetailsButton,
  type ObjectDetailsButtonProps,
} from "@/shared/components/menu/object-details-button";
import { ARTIFACT_OBJECT } from "@/shared/config/constants";

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
