import { useAtomValue } from "jotai";

import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerLinkButton } from "@/shared/components/data-viewer/data-viewer-action-button";
import { DataViewerCopyButton } from "@/shared/components/data-viewer/data-viewer-copy-button";
import { DataViewerDownloadButton } from "@/shared/components/data-viewer/data-viewer-download-button";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { isCopyableContentType } from "@/shared/utils/file";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  getObjectFileDownloadUrl,
  getObjectFileRawUrl,
} from "@/entities/object-file/domain/get-object-file";
import { useGetObjectFile } from "@/entities/object-file/domain/get-object-file.query";

export interface ObjectFileProps {
  nodeId: string;
  fileName: string;
  contentType?: DataViewerContentType;
  className?: string;
}

export function ObjectFile({ nodeId, fileName, contentType, className }: ObjectFileProps) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);
  const { data, isPending, error } = useGetObjectFile({ nodeId, contentType });

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <NoDataFound message={error.message} />;
  }

  if (!data) {
    return null;
  }

  const urlParams = { nodeId, branchName: currentBranch.name, atDate };
  const rawUrl = getObjectFileRawUrl(urlParams);
  const downloadUrl = getObjectFileDownloadUrl(urlParams);

  return (
    <DataViewer
      title={fileName}
      data={data}
      contentType={contentType}
      className={className}
      actions={
        <>
          <DataViewerLinkButton href={rawUrl} target="_blank" rel="noopener noreferrer">
            Raw
          </DataViewerLinkButton>
          <DataViewerDownloadButton
            data={data}
            fileName={fileName}
            contentType={contentType}
            downloadUrl={downloadUrl}
          />
          {isCopyableContentType(contentType) && <DataViewerCopyButton data={data} />}
        </>
      }
    />
  );
}
