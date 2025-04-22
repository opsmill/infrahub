import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import {
  ObjectDetailsButton,
  ObjectDetailsButtonProps,
} from "@/shared/components/menu/object-details-button";
import { DropdownMenuItem } from "@/shared/components/ui/dropdown-menu";

export interface ArtifactDetailsMenuProps extends ObjectDetailsButtonProps {
  checksum?: string;
  storageId?: string;
}

export function ArtifactDetailsMenu({ id, hfid, checksum, storageId }: ArtifactDetailsMenuProps) {
  return (
    <ObjectDetailsButton id={id} hfid={hfid}>
      {checksum && (
        <DropdownMenuItem className="p-0">
          <CopyToClipboard
            size={"default"}
            className="grow justify-start gap-2 p-2"
            text={checksum}
          >
            Copy Checksum
          </CopyToClipboard>
        </DropdownMenuItem>
      )}

      {storageId && (
        <DropdownMenuItem className="p-0">
          <CopyToClipboard
            size={"default"}
            className="grow justify-start gap-2 p-2"
            text={storageId}
          >
            Copy Storage ID
          </CopyToClipboard>
        </DropdownMenuItem>
      )}
    </ObjectDetailsButton>
  );
}
