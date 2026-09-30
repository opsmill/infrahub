import { FolderGitIcon } from "lucide-react";

import { Link } from "@/shared/components/ui/link";

import { getBranchQsp } from "@/entities/branches/ui/routing/branch-urls";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";

interface RepositoryNameLinkProps {
  repository: BranchRepository;
  branchName: string;
}

export function RepositoryNameLink({ repository, branchName }: RepositoryNameLinkProps) {
  const { id, kind, name, isReadOnly } = repository;

  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <FolderGitIcon className="size-3.5 shrink-0 text-foreground-muted" aria-hidden />
      <Link
        to={getObjectDetailsUrl(kind, id, [getBranchQsp(branchName)])}
        title={name}
        className="truncate"
      >
        {name}
      </Link>
      {isReadOnly && (
        <span className="shrink-0 rounded bg-content-strong px-1 text-foreground-muted text-xs">
          Read-only
        </span>
      )}
    </div>
  );
}
