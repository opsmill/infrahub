import type { ReactNode } from "react";

import { Col, Row } from "@/shared/components/container";
import { DataViewerDownloadLinkButton } from "@/shared/components/data-viewer/data-viewer-download-link-button";
import { DataViewerRawButton } from "@/shared/components/data-viewer/data-viewer-raw-button";

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
            {url && <DataViewerRawButton href={url} />}
            {downloadUrl && <DataViewerDownloadLinkButton href={downloadUrl} fileName={fileName} />}
          </>
        )}
      </Row>
      {children}
    </Col>
  );
}
