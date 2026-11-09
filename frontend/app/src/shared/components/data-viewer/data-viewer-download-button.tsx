import { Tooltip } from "@infrahub/ui";
import { DownloadIcon } from "lucide-react";

import { dataViewerActionStyle } from "@/shared/components/data-viewer/data-viewer.styles";
import { Download, type DownloadProps } from "@/shared/components/download";
import { classNames } from "@/shared/utils/common";

export function DataViewerDownloadButton({ className, ...props }: Omit<DownloadProps, "children">) {
  return (
    <Tooltip message="Download">
      <Download className={classNames(...dataViewerActionStyle, className)} {...props}>
        <DownloadIcon className="size-4" />
      </Download>
    </Tooltip>
  );
}
