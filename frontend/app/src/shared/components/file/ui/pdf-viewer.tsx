import { DownloadIcon, ExternalLinkIcon } from "lucide-react";

import { Tooltip } from "@/shared/components/aria/tooltip";
import { Col, Row } from "@/shared/components/container";

import type { FileViewerBaseProps } from "./types";

export function PdfViewer({ url, downloadUrl, fileName }: FileViewerBaseProps) {
  return (
    <Col className="grow rounded-lg bg-neutral-800 p-2 text-neutral-200">
      <Row>
        <span className="grow px-1 font-medium">PDF</span>
        <Tooltip message="Download">
          <a
            href={downloadUrl ?? url}
            download={fileName}
            className="rounded-lg border border-transparent p-1 text-sm hover:bg-neutral-600"
          >
            <DownloadIcon className="size-4" />
          </a>
        </Tooltip>
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
      </Row>

      <iframe
        src={url}
        title={fileName}
        className="h-150 w-full rounded-lg border border-neutral-700"
      />
    </Col>
  );
}
