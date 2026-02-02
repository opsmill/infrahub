import { getFileIcon } from "@/shared/utils/file";

import { EmbedViewer } from "./embed-viewer";

interface FileViewerFallbackProps {
  url?: string;
  downloadUrl?: string;
  fileName: string;
  contentType?: string;
}

export function FileViewerFallback({
  url,
  downloadUrl,
  fileName,
  contentType,
}: FileViewerFallbackProps) {
  const FileIconComponent = getFileIcon(contentType);

  return (
    <EmbedViewer title="Preview" url={url} downloadUrl={downloadUrl} fileName={fileName}>
      <div className="flex flex-col items-center justify-center rounded-lg border border-neutral-700 py-12 text-center">
        <FileIconComponent className="mb-3 size-12 text-neutral-500" />
        <p className="text-neutral-400 text-sm">Preview not available for this file type</p>
      </div>
    </EmbedViewer>
  );
}
