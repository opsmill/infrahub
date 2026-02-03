import { Tooltip } from "@/shared/components/aria/tooltip";

import { DataViewerLinkButton } from "./data-viewer-action-button";

interface DataViewerRawButtonProps {
  href: string;
}

export function DataViewerRawButton({ href }: DataViewerRawButtonProps) {
  return (
    <Tooltip message="Raw">
      <DataViewerLinkButton href={href} target="_blank" rel="noopener noreferrer">
        Raw
      </DataViewerLinkButton>
    </Tooltip>
  );
}
