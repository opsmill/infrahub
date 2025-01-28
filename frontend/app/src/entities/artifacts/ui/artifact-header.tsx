import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { ObjectDetailsButton } from "@/shared/components/menu/object-details-button";
import { Badge } from "@/shared/components/ui/badge";
import { DropdownMenuItem } from "@/shared/components/ui/dropdown-menu";
import { Generate } from "./generate";

type ArtifactHeaderProps = {
  id: string;
  hfid?: string;
  name?: string;
  status?: string;
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
    <div className="flex flex-grow justify-between">
      <div className="flex items-center gap-3">
        <h1 className="font-bold text-xl">{name}</h1>

        <ObjectDetailsButton id={id} hfid={hfid}>
          {checksum && (
            <DropdownMenuItem className="p-0">
              <CopyToClipboard
                size={"default"}
                className="flex-grow justify-start gap-2 p-2"
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
                className="flex-grow justify-start gap-2 p-2"
                text={storageId}
              >
                Copy Storage ID
              </CopyToClipboard>
            </DropdownMenuItem>
          )}
        </ObjectDetailsButton>

        <Badge>{status}</Badge>
      </div>

      {definitionId && <Generate label="Re-generate" artifactid={id} definitionid={definitionId} />}
    </div>
  );
};

export default ArtifactHeader;
