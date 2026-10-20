import { getBranchQsp } from "@/entities/branches/ui/routing/branch-urls";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type {
  BranchRepository,
  RepositoryImportError,
} from "@/entities/repository/domain/model/branch-repository";
import { RepositoryErrorBand } from "@/entities/repository/ui/branch-repositories/repository-error-band";
import { useGetRepositoryImportError } from "@/entities/repository/ui/queries/get-repository-import-error.query";
import { getTaskDetailsUrl } from "@/entities/tasks/ui/routing/task-urls";

interface ImportErrorBandProps {
  repository: BranchRepository;
  branchName: string;
  isSyncing: boolean;
}

export function ImportErrorBand({ repository, branchName, isSyncing }: ImportErrorBandProps) {
  const importError = useGetRepositoryImportError({
    branchName,
    repositoryId: repository.id,
    isSyncing,
  });

  return (
    <RepositoryErrorBand
      tone="danger"
      repositoryName={repository.name}
      problem="import failed"
      action={getImportErrorAction(importError, repository, branchName)}
    >
      <ImportErrorDetails importError={importError} />
    </RepositoryErrorBand>
  );
}

function getImportErrorAction(
  importError: RepositoryImportError | undefined,
  repository: BranchRepository,
  branchName: string
) {
  if (!importError) return;
  if (importError.taskId) {
    return { to: getTaskDetailsUrl(importError.taskId), label: "View task log →" };
  }
  return {
    to: getObjectDetailsUrl(repository.kind, repository.id, [getBranchQsp(branchName)]),
    label: "Open repository",
  };
}

function ImportErrorDetails({ importError }: { importError: RepositoryImportError | undefined }) {
  if (!importError) {
    return <p className="text-foreground-muted text-xs">Loading the import log…</p>;
  }

  if (importError.status === "not-found") {
    return (
      <p className="text-danger-strong text-xs">
        The error details couldn't be found for this import.
      </p>
    );
  }

  return (
    <p className="whitespace-pre-wrap break-words font-mono text-danger-strong text-xs leading-relaxed">
      {importError.message}
    </p>
  );
}
