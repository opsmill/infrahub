import { DownloadIcon, ExternalLinkIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Tooltip } from "@/shared/components/aria/tooltip";
import { Col, Row } from "@/shared/components/container";

import type { FileViewerBaseProps } from "./types";

interface EmbedViewerProps extends Partial<FileViewerBaseProps> {
  title: string;
  children: ReactNode;
}

export function EmbedViewer({ title, url, downloadUrl, fileName, children }: EmbedViewerProps) {
  const hasActions = url || downloadUrl;

  return (
    <Col className="grow rounded-lg bg-neutral-800 p-2 text-neutral-200">
      <Row>
        <span className="grow px-1 font-medium">{title}</span>
        {hasActions && (
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
      {children}
    </Col>
  );
}
