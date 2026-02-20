import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetFilesDiff } from "@/entities/diff/domain/get-files-diff.query";
import {
  DiffBranchNotFound,
  isBranchNotFoundError,
} from "@/entities/diff/ui/diff-branch-not-found";
import { FileRepoDiff } from "@/entities/diff/ui/file-diff/file-repo-diff";

interface FilesDiffProps {
  branchName: string;
}

export function FilesDiff({ branchName }: FilesDiffProps) {
  const { data: filesDiff, isLoading, error } = useGetFilesDiff({ branchName });

  if (isLoading) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    if (isBranchNotFoundError(error)) {
      return <DiffBranchNotFound branchName={branchName} />;
    }
    return <ErrorScreen message={error.message} />;
  }

  if (!filesDiff?.length) {
    return <NoDataFound message="No files diff for this branch." />;
  }

  return (
    <Col className="gap-4 p-4">
      {filesDiff.map((diff) => (
        <FileRepoDiff key={diff.id} diff={diff} />
      ))}
    </Col>
  );
}
