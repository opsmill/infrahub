import { AlertCircleIcon, LockIcon } from "lucide-react";

import { Skeleton } from "@/shared/components/loading/skeleton";

export function BranchRepositoriesLoading() {
  return (
    <div role="status" aria-busy="true">
      <span className="sr-only">Loading repositories</span>
      {[0, 1, 2].map((index) => (
        <div key={index} className="flex h-10 items-center gap-4 border-b px-3 last:border-b-0">
          <Skeleton className="h-3 w-1/3" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-3 w-14" />
        </div>
      ))}
    </div>
  );
}

export function BranchRepositoriesDenied() {
  return (
    <div className="flex items-start gap-2 px-4 py-4 text-sm">
      <LockIcon className="mt-0.5 size-4 shrink-0 text-foreground-muted" aria-hidden />
      <div>
        <p className="font-medium">You don't have access to this branch's repositories</p>
        <p className="text-foreground-muted">
          Ask an administrator for permission to view repositories.
        </p>
      </div>
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  description: string;
}

function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="px-4 py-6 text-center text-sm">
      <p className="font-medium">{title}</p>
      <p className="mx-auto mt-1 max-w-prose text-pretty text-foreground-muted">{description}</p>
    </div>
  );
}

export function BranchRepositoriesNotSynced() {
  return (
    <EmptyState
      title="Not synchronised with Git"
      description="This branch was created with Sync with Git off, so repository imports and generators don't run on it."
    />
  );
}

export function BranchRepositoriesNone() {
  return (
    <EmptyState
      title="No Git repositories"
      description="Repositories connected to Infrahub will show here with their Git state on this branch."
    />
  );
}

export function BranchRepositoryHealthFailed() {
  return (
    <div role="alert" className="flex items-center gap-2 border-t px-4 py-2 text-danger text-xs">
      <AlertCircleIcon className="size-4 shrink-0" aria-hidden />
      Repository health couldn't be checked. Retrying…
    </div>
  );
}

export function BranchRepositoriesFailed() {
  return (
    <div role="alert" className="flex items-center gap-2 px-4 py-4 text-danger text-sm">
      <AlertCircleIcon className="size-4 shrink-0" aria-hidden />
      Repositories couldn't be loaded.
    </div>
  );
}
