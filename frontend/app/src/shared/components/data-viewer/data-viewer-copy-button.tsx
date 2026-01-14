import { CopyCheckIcon, CopyIcon } from "lucide-react";

import { Tooltip } from "@/shared/components/aria/tooltip";
import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

import { DataViewerActionButton } from "./data-viewer-action-button";

export function DataViewerCopyButton({ value }: { value: string }) {
  const { isCopied, copyToClipboard } = useCopyToClipboard();

  return (
    <Tooltip message={isCopied ? "Copied!" : "Copy"}>
      <DataViewerActionButton onPress={() => copyToClipboard(value)}>
        {isCopied ? <CopyCheckIcon className="size-4" /> : <CopyIcon className="size-4" />}
      </DataViewerActionButton>
    </Tooltip>
  );
}
