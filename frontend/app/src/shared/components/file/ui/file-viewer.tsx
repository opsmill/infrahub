import { EmbedViewer } from "./embed-viewer";
import { FileViewerFallback } from "./file-viewer-fallback";
import { TextFileViewer } from "./text-file-viewer";
import { getViewerType } from "./utils";

export interface FileViewerProps {
  url: string;
  downloadUrl?: string;
  fileName: string;
  contentType?: string;
}

export function FileViewer({ url, downloadUrl, fileName, contentType }: FileViewerProps) {
  const viewerType = getViewerType(contentType);

  switch (viewerType.type) {
    case "text":
      return (
        <TextFileViewer
          url={url}
          fileName={fileName}
          contentType={viewerType.dataViewerContentType}
        />
      );

    case "image":
      return (
        <EmbedViewer title="Image" url={url} downloadUrl={downloadUrl} fileName={fileName}>
          <div className="flex justify-center rounded-lg border border-neutral-700 bg-white p-4">
            <img src={url} alt={fileName} className="max-h-150 max-w-full rounded" />
          </div>
        </EmbedViewer>
      );

    case "pdf":
      return (
        <EmbedViewer title="PDF" url={url} downloadUrl={downloadUrl} fileName={fileName}>
          <iframe
            src={url}
            title={fileName}
            className="h-150 w-full rounded-lg border border-neutral-700"
          />
        </EmbedViewer>
      );

    case "unsupported":
      return (
        <FileViewerFallback
          url={url}
          downloadUrl={downloadUrl}
          fileName={fileName}
          contentType={contentType}
        />
      );
  }
}
