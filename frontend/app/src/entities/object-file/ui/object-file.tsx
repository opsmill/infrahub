import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetObjectFile } from "@/entities/object-file/domain/get-object-file.query";

export interface ObjectFileProps {
  nodeId: string;
  fileName: string;
  contentType?: string;
  className?: string;
}

export function ObjectFile({ nodeId, fileName, contentType, className }: ObjectFileProps) {
  const { data: content, isPending, error } = useGetObjectFile({ nodeId });

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <NoDataFound message={error.message} />;
  }

  if (!content) {
    return <NoDataFound message="File content is empty" />;
  }

  return (
    <DataViewer
      data={content}
      fileName={fileName}
      contentType={contentType}
      className={className}
    />
  );
}
