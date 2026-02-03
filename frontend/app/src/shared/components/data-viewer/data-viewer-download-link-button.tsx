import { DownloadIcon } from "lucide-react";

import { Tooltip } from "@/shared/components/aria/tooltip";

import { DataViewerLinkButton } from "./data-viewer-action-button";

interface DataViewerDownloadLinkButtonProps {
  href: string;
  fileName?: string;
}

export function DataViewerDownloadLinkButton({
  href,
  fileName,
}: DataViewerDownloadLinkButtonProps) {
  return (
    <Tooltip message="Download">
      <DataViewerLinkButton href={href} download={fileName}>
        <DownloadIcon className="size-4" />
      </DataViewerLinkButton>
    </Tooltip>
  );
}
