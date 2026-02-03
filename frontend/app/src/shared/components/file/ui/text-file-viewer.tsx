import { CONTENT_TYPE_CONFIG, DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerLinkButton } from "@/shared/components/data-viewer/data-viewer-action-button";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetFileContent } from "../domain/get-file-content.query";
import type { FileViewerBaseProps } from "./types";

interface TextFileViewerProps extends FileViewerBaseProps {
  contentType: DataViewerContentType;
}

export function TextFileViewer({ url, downloadUrl, fileName, contentType }: TextFileViewerProps) {
  const { data: fileContent, isPending, error } = useGetFileContent({ url });

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <NoDataFound message={error.message} />;
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
