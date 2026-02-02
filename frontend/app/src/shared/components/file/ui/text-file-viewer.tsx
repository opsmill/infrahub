import { useEffect } from "react";
import { toast } from "react-toastify";

import { CONTENT_TYPE_CONFIG, DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerLinkButton } from "@/shared/components/data-viewer/data-viewer-action-button";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useGetFileContent } from "../domain/get-file-content.query";
import type { FileViewerBaseProps } from "./types";

interface TextFileViewerProps extends FileViewerBaseProps {
  contentType: DataViewerContentType;
}

export function TextFileViewer({ url, downloadUrl, fileName, contentType }: TextFileViewerProps) {
  const { data: fileContent, isPending, isError } = useGetFileContent({ url });

  useEffect(() => {
    if (isError) {
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading file content" />);
    }
  }, [isError]);

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (!fileContent) {
    return <NoDataFound message="No file found." />;
  }

  const config = CONTENT_TYPE_CONFIG[contentType] ?? CONTENT_TYPE_CONFIG["text/plain"];

  return (
    <DataViewer
      title={config.label}
      data={fileContent}
      fileName={fileName}
      contentType={contentType}
      actions={
        <>
          {downloadUrl && (
            <DataViewerLinkButton href={downloadUrl} download={fileName}>
              Download
            </DataViewerLinkButton>
          )}
          <DataViewerLinkButton href={url} target="_blank" rel="noopener noreferrer">
            Raw
          </DataViewerLinkButton>
        </>
      }
    />
  );
}
