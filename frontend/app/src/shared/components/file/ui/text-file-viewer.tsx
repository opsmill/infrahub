import { CONTENT_TYPE_CONFIG, DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerRawButton } from "@/shared/components/data-viewer/data-viewer-raw-button";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetFileContent } from "../domain/get-file-content.query";
import type { FileViewerBaseProps } from "./types";

interface TextFileViewerProps extends FileViewerBaseProps {
  contentType: DataViewerContentType;
}

export function TextFileViewer({ url, fileName, contentType }: TextFileViewerProps) {
  const { data: fileContent, isPending, error } = useGetFileContent({ url });

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <NoDataFound message={error.message} />;
  }

  if (fileContent === null) {
    return <NoDataFound message="File content is empty" />;
  }

  const config = CONTENT_TYPE_CONFIG[contentType] ?? CONTENT_TYPE_CONFIG["text/plain"];

  return (
    <DataViewer
      title={config.label}
      data={fileContent}
      fileName={fileName}
      contentType={contentType}
      actions={<DataViewerRawButton href={url} />}
    />
  );
}
