import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { ArtifactRepoDiff } from "@/entities/diff/artifact-diff/artifact-repo-diff";
import { useGetArtifactsDiff } from "@/entities/diff/domain/get-artifacts-diff.query";

interface ArtifactsDiffProps {
  branchName: string;
}

export function ArtifactsDiff({ branchName }: ArtifactsDiffProps) {
  const { data: sortedArtifacts, isPending, error } = useGetArtifactsDiff({ branch: branchName });

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (!sortedArtifacts?.length) {
    return <NoDataFound message="No artifact found." />;
  }

  return (
    <Col className="gap-4 p-4">
      {sortedArtifacts.map((diff) => (
        <ArtifactRepoDiff key={diff.id} diff={diff} />
      ))}
    </Col>
  );
}
