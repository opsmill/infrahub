import { AlertCircleIcon } from "lucide-react";

import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "@/shared/components/ui/link";

import { getBranchQspOverride } from "@/entities/branches/ui/routing/branch-urls";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import type { RepositoryImportError } from "@/entities/repository/domain/use-cases/get-repository-import-error";
import { useGetRepositoryImportError } from "@/entities/repository/ui/queries/get-repository-import-error.query";

interface ImportErrorBandProps {
  repository: BranchRepository;
  branchName: string;
  isDefaultBranch: boolean;
  isSyncing: boolean;
}

export function ImportErrorBand({
  repository,
  branchName,
  isDefaultBranch,
  isSyncing,
}: ImportErrorBandProps) {
  const { data } = useGetRepositoryImportError({
    branchName,
    repositoryId: repository.id,
    isSyncing,
  });

  return (
    <div
      className="flex items-start gap-2.5 border-danger/30 border-t bg-danger-surface px-4 py-3"
      data-testid="repository-error-band"
      role="status"
    >
      <AlertCircleIcon className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="font-semibold text-danger-strong text-sm">
          <span className="break-all">{repository.name}</span> — import failed
        </div>
        <ImportErrorDetails importError={data} />
      </div>
      <ImportErrorLink
        importError={data}
        repository={repository}
        branchName={branchName}
        isDefaultBranch={isDefaultBranch}
      />
    </div>
  );
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

interface ImportErrorLinkProps {
  importError: RepositoryImportError | undefined;
  repository: BranchRepository;
  branchName: string;
  isDefaultBranch: boolean;
}

function ImportErrorLink({
  importError,
  repository,
  branchName,
  isDefaultBranch,
}: ImportErrorLinkProps) {
  if (!importError) return null;

  const linkClassName = "shrink-0 px-2 py-1 font-medium text-danger-strong text-xs";

  if (importError.taskId) {
    return (
      <Link to={constructPath(`/tasks/${importError.taskId}`)} className={linkClassName}>
        View task log →
      </Link>
    );
  }

  return (
    <Link
      to={getObjectDetailsUrl(repository.kind, repository.id, [
        getBranchQspOverride(branchName, isDefaultBranch),
      ])}
      className={linkClassName}
    >
      Open repository
    </Link>
  );
}
