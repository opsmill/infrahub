import { CopyCheckIcon, CopyIcon } from "lucide-react";

import { Tooltip } from "@/shared/components/aria/tooltip";
import { DataViewerActionButton } from "@/shared/components/data-viewer/data-viewer-action-button";
import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

export function DataViewerCopyButton({ data }: { data: string }) {
  const { isCopied, copyToClipboard } = useCopyToClipboard();

  return (
    <Tooltip message={isCopied ? "Copied!" : "Copy"}>
      <DataViewerActionButton onPress={() => copyToClipboard(data)}>
        {isCopied ? <CopyCheckIcon className="size-4" /> : <CopyIcon className="size-4" />}
      </DataViewerActionButton>
    </Tooltip>
  );
}
