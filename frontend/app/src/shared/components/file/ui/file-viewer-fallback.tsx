import { DownloadIcon, ExternalLinkIcon } from "lucide-react";

import { Tooltip } from "@/shared/components/aria/tooltip";
import { Col, Row } from "@/shared/components/container";
import { getFileIcon } from "@/shared/utils/file";

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
    <Col className="grow rounded-lg bg-neutral-800 p-2 text-neutral-200">
      <Row>
        <span className="grow px-1 font-medium">Preview</span>
        {(url || downloadUrl) && (
          <>
            <Tooltip message="Download">
              <a
                href={downloadUrl ?? url}
                download={fileName}
                className="rounded-lg border border-transparent p-1 text-sm hover:bg-neutral-600"
              >
                <DownloadIcon className="size-4" />
              </a>
            </Tooltip>
            {url && (
              <Tooltip message="Open in new tab">
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-transparent p-1 text-sm hover:bg-neutral-600"
                >
                  <ExternalLinkIcon className="size-4" />
                </a>
              </Tooltip>
            )}
          </>
        )}
      </Row>

      <div className="flex flex-col items-center justify-center rounded-lg border border-neutral-700 py-12 text-center">
        <FileIconComponent className="mb-3 size-12 text-neutral-500" />
        <p className="text-neutral-400 text-sm">Preview not available for this file type</p>
      </div>
    </Col>
  );
}
