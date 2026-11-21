import { useParams } from "react-router";

import { Row } from "@/shared/components/container";
import Accordion from "@/shared/components/display/accordion";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import type { FileDiffFile } from "@/entities/diff/domain/use-cases/get-files-diff";
import { CommentableContentDiff } from "@/entities/diff/ui/content-diff/commentable-content-diff";
import { DiffBadge } from "@/entities/diff/ui/node-diff/utils";
import { useGetFile } from "@/entities/diff/ui/queries/get-file.query";
import { useGetFileContentDiff } from "@/entities/diff/ui/queries/get-file-content-diff.query";
import { PROPOSED_CHANGES_FILE_THREAD_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change-thread";

interface FileContentDiffProps {
  repositoryId: string;
  repositoryDisplayName?: string | null;
  file: FileDiffFile;
  commitFrom: string;
  commitTo: string;
}

export function FileContentDiff({
  repositoryId,
  repositoryDisplayName,
  file,
  commitFrom,
  commitTo,
}: FileContentDiffProps) {
  const { proposedChangeId } = useParams();

  const {
    data: previousFile,
    isPending: isPendingPreviousFile,
    error: previousFileError,
  } = useGetFile({
    repositoryId,
    filePath: file.location,
    commit: commitFrom,
  });

  const {
    data: newFile,
    isPending: isPendingNewFile,
    error: newFileError,
  } = useGetFile({
    repositoryId,
    filePath: file.location,
    commit: commitTo,
  });

  const {
    isLoading: isThreadsLoading,
    error,
    data,
    refetch,
  } = useGetFileContentDiff(
    { proposedChangeId: proposedChangeId ?? "" },
    { enabled: !!proposedChangeId }
  );

  if (isThreadsLoading || isPendingPreviousFile || isPendingNewFile) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error || previousFileError || newFileError) {
    return <ErrorScreen message="Something went wrong when fetching the file differences." />;
  }

  if (!previousFile && !newFile) {
    return null;
  }

  return (
    <div className={"m-4 rounded-lg bg-content p-2 shadow-sm"}>
      <Accordion
        title={
          <Row>
            <DiffBadge status={file.action.toUpperCase()} />
            {file.location}
          </Row>
        }
      >
        <CommentableContentDiff
          previousContent={previousFile ?? ""}
          newContent={newFile ?? ""}
          previousLabel={commitFrom && `Commit: ${commitFrom}`}
          newLabel={commitTo && `Commit: ${commitTo}`}
          proposedChangeId={proposedChangeId}
          threads={data?.threads ?? []}
          onThreadsChange={refetch}
          isThreadOnSide={(thread, side) => {
            const threadCommit = thread.commit?.value;

            if (side === "new") {
              return threadCommit === commitTo;
            }

            return threadCommit === commitFrom || !threadCommit === !commitFrom;
          }}
          threadKind={PROPOSED_CHANGES_FILE_THREAD_OBJECT}
          buildThreadData={({ side, lineNumber }) => ({
            label: {
              value: `${repositoryDisplayName} - ${file.location}:${lineNumber}`,
            },
            commit: {
              value: side === "new" ? commitTo : commitFrom,
            },
            file: {
              value: file.location,
            },
            repository: {
              id: repositoryId,
            },
          })}
        />
      </Accordion>
    </div>
  );
}
