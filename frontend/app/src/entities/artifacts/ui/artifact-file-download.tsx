import { ArtifactFileButton } from "@/entities/artifacts/ui/artifact-file-button";
import { Download, DownloadProps } from "@/shared/components/download";
import { DownloadIcon } from "lucide-react";

export const ArtifactFileDownload = ({ className, ...props }: DownloadProps) => {
  return (
    <Download className="inline-flex" {...props}>
      <ArtifactFileButton className={className}>
        <DownloadIcon className="size-4" />
      </ArtifactFileButton>
    </Download>
  );
};
