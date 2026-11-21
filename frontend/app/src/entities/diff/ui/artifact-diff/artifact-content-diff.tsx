import { useParams } from "react-router";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetArtifactFile } from "@/entities/artifacts/ui/queries/get-artifact-file.query";
import { CommentableContentDiff } from "@/entities/diff/ui/content-diff/commentable-content-diff";
import type { DiffSide } from "@/entities/diff/ui/content-diff/line-comments";
import { useGetArtifactContentDiff } from "@/entities/diff/ui/queries/get-artifact-content-diff.query";
import { PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change-thread";

interface ArtifactContentDiffProps {
  id: string; // required artifact node ID
  itemPrevious?: { storage_id?: string } | null;
  itemNew?: { storage_id?: string } | null;
}

export const ArtifactContentDiff = ({ itemPrevious, itemNew, id }: ArtifactContentDiffProps) => {
  const { proposedChangeId } = useParams();
  const {
    data: previousFile = "",
    isLoading: isPreviousLoading,
    error: previousFileError,
  } = useGetArtifactFile(
    { storageId: itemPrevious?.storage_id ?? "" },
    { enabled: !!itemPrevious?.storage_id }
  );

  const {
    data: newFile = "",
    isLoading: isNewLoading,
    error: newFileError,
  } = useGetArtifactFile(
    { storageId: itemNew?.storage_id ?? "" },
    { enabled: !!itemNew?.storage_id }
  );

  const {
    isLoading: isThreadsLoading,
    error,
    data,
    refetch,
  } = useGetArtifactContentDiff(
    { proposedChangeId: proposedChangeId ?? "" },
    { enabled: !!proposedChangeId }
  );

  if (isThreadsLoading || isPreviousLoading || isNewLoading) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error || previousFileError || newFileError) {
    return <ErrorScreen message="Something went wrong when fetching the artifact content." />;
  }

  if (!previousFile && !newFile) {
    return null;
  }

  const getStorageId = (side: DiffSide) =>
    side === "new" ? itemNew?.storage_id : itemPrevious?.storage_id;

  return (
    <div className={"pr-2 pb-2"}>
      <CommentableContentDiff
        previousContent={previousFile}
        newContent={newFile}
        previousLabel={itemPrevious?.storage_id && `Storage id: ${itemPrevious.storage_id}`}
        newLabel={itemNew?.storage_id && `Storage id: ${itemNew.storage_id}`}
        proposedChangeId={proposedChangeId}
        threads={data?.threads ?? []}
        onThreadsChange={refetch}
        isThreadOnSide={(thread, side) => thread.storage_id?.value === getStorageId(side)}
        threadKind={PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT}
        buildThreadData={({ side }) => ({
          storage_id: {
            value: getStorageId(side),
          },
          artifact_id: {
            value: id,
          },
        })}
      />
    </div>
  );
};
