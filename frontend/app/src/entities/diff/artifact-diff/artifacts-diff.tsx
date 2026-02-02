import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetArtifactsDiff } from "@/entities/diff/domain/get-artifacts-diff.query";

import "react-diff-view/style/index.css";

import { ArtifactRepoDiff } from "./artifact-repo-diff";

interface ArtifactsDiffProps {
  branchName: string;
}

export function ArtifactsDiff({ branchName }: ArtifactsDiffProps) {
  const { data: sortedArtifacts, isLoading } = useGetArtifactsDiff({ branch: branchName });

  if (isLoading) {
    return <LoadingIndicator className="p-4" />;
  }

  if (!sortedArtifacts?.length) {
    return <NoDataFound message="No artifact found." />;
  }

  return (
    <div className="text-sm">
      {sortedArtifacts.map((diff) => (
        <ArtifactRepoDiff key={diff.id} diff={diff} />
      ))}
    </div>
  );
}
