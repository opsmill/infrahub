import { Col, Row } from "@/shared/components/container";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { classNames } from "@/shared/utils/common";
import { getFileIcon } from "@/shared/utils/file";

import { CONTENT_TYPE_CONFIG, DataViewer } from "./data-viewer";
import { DataViewerDownloadLinkButton } from "./data-viewer-download-link-button";
import { DataViewerRawButton } from "./data-viewer-raw-button";
import { getViewerType } from "./types";
import { useGetFileContent } from "./use-get-file-content";

export interface FileViewerProps {
  /** URL to fetch content from */
  url: string;
  /** File name used for download operations */
  fileName: string;
  /** MIME content type - determines rendering mode */
  contentType?: string;
  /** Separate download URL if different from content URL */
  downloadUrl?: string;
  /** Additional CSS classes */
  className?: string;
}

export function FileViewer({
  url,
  fileName,
  contentType,
  downloadUrl,
  className,
}: FileViewerProps) {
  const viewerType = getViewerType(contentType);

  // Only fetch for text content types
  const shouldFetch = viewerType.type === "text";
  const { data: content, isPending, error } = useGetFileContent(shouldFetch ? url : null);

  if (shouldFetch && isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (shouldFetch && error) {
    return <NoDataFound message={error.message} />;
  }

  // Text content - use DataViewer
  if (viewerType.type === "text") {
    if (!content) {
      return <NoDataFound message="File content is empty" />;
    }

    const config = CONTENT_TYPE_CONFIG[viewerType.dataViewerContentType];

    return (
      <DataViewer
        title={config?.label ?? "Text"}
        data={content}
        fileName={fileName}
        contentType={viewerType.dataViewerContentType}
        actions={<DataViewerRawButton href={url} />}
        className={className}
      />
    );
  }

  // Non-text content (image, PDF, unsupported)
  return (
    <Col className={classNames("grow rounded-lg bg-neutral-800 p-2 text-neutral-200", className)}>
      <Row>
        <span className="grow px-1 font-medium">Preview</span>
        <DataViewerRawButton href={url} />
        <DataViewerDownloadLinkButton href={downloadUrl ?? url} fileName={fileName} />
      </Row>

      <FileContent
        viewerType={viewerType}
        url={url}
        fileName={fileName}
        contentType={contentType}
      />
    </Col>
  );
}

interface FileContentProps {
  viewerType: ReturnType<typeof getViewerType>;
  url: string;
  fileName: string;
  contentType?: string;
}

function FileContent({ viewerType, url, fileName, contentType }: FileContentProps) {
  switch (viewerType.type) {
    case "image": {
      return (
        <div className="flex justify-center rounded-lg border border-neutral-700 bg-white p-4">
          <img src={url} alt={fileName} className="max-h-150 max-w-full rounded" />
        </div>
      );
    }

    case "pdf": {
      return (
        <iframe
          src={url}
          title={fileName}
          className="h-150 w-full rounded-lg border border-neutral-700"
        />
      );
    }

    case "unsupported": {
      const FileIconComponent = getFileIcon(contentType);
      return (
        <div className="flex flex-col items-center justify-center rounded-lg border border-neutral-700 py-12 text-center">
          <FileIconComponent className="mb-3 size-12 text-neutral-500" />
          <p className="text-neutral-400 text-sm">Preview not available for this file type</p>
        </div>
      );
    }

    default: {
      return null;
    }
  }
}
