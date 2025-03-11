import { Download, DownloadProps } from "@/shared/components/download";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { DownloadIcon } from "lucide-react";

export const ArtifactFileDownload = ({ className, ...props }: DownloadProps) => {
  return (
    <Download
      className={classNames(
        focusVisibleStyle,
        "border border-transparent p-1 hover:bg-neutral-600 rounded-lg",
        className
      )}
      {...props}
    >
      <DownloadIcon className="size-4" />
    </Download>
  );
};
