import { FileViewerFallback } from "./file-viewer-fallback";
import { ImageViewer } from "./image-viewer";
import { PdfViewer } from "./pdf-viewer";
import { TextFileViewer } from "./text-file-viewer";
import { mapToDataViewerContentType } from "./utils";

export interface FileViewerProps {
  url: string;
  downloadUrl?: string;
  fileName: string;
  contentType?: string;
}

export function FileViewer({ url, downloadUrl, fileName, contentType }: FileViewerProps) {
  const dataViewerContentType = mapToDataViewerContentType(contentType);

  // For text-based content, we need to fetch and display with DataViewer
  if (dataViewerContentType) {
    return (
      <TextFileViewer
        url={url}
        downloadUrl={downloadUrl}
        fileName={fileName}
        contentType={dataViewerContentType}
      />
    );
  }

  // For images (except SVG which is handled above)
  if (contentType?.startsWith("image/")) {
    return <ImageViewer url={url} downloadUrl={downloadUrl} fileName={fileName} />;
  }

  // For PDFs
  if (contentType === "application/pdf") {
    return <PdfViewer url={url} downloadUrl={downloadUrl} fileName={fileName} />;
  }

  // Fallback for unsupported types
  return (
    <FileViewerFallback
      url={url}
      downloadUrl={downloadUrl}
      fileName={fileName}
      contentType={contentType}
    />
  );
}
