import { DownloadIcon } from "lucide-react";

import { Download, type DownloadProps } from "@/shared/components/download";

import { ArtifactFileButton } from "@/entities/artifacts/ui/artifact-file-button";

export const ArtifactFileDownload = ({ className, ...props }: DownloadProps) => {
  return (
    <Download className="inline-flex" {...props}>
      <ArtifactFileButton className={className}>
        <DownloadIcon className="size-4" />
      </ArtifactFileButton>
    </Download>
  );
};
