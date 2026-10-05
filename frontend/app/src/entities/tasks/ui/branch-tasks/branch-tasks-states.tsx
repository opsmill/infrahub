import { Button } from "@infrahub/ui";
import { AlertCircleIcon } from "lucide-react";

import { Skeleton } from "@/shared/components/loading/skeleton";

export function BranchTasksLoading() {
  return (
    <div role="status" aria-busy="true">
      <span className="sr-only">Loading tasks</span>
      {[0, 1, 2].map((index) => (
        <div key={index} className="flex h-10 items-center gap-4 border-b px-3 last:border-b-0">
          <Skeleton className="h-3 w-2/5" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-3 w-16" />
        </div>
      ))}
    </div>
  );
}

export function BranchTasksNone() {
  return (
    <p className="px-4 py-6 text-center text-foreground-muted text-sm">
      No tasks have run on this branch yet. Imports, generators and validations appear here as they
      run.
    </p>
  );
}

interface BranchTasksFailedProps {
  onGoToFirstPage?: () => void;
}

export function BranchTasksFailed({ onGoToFirstPage }: BranchTasksFailedProps) {
  return (
    <div role="alert" className="flex items-center gap-2 px-4 py-4 text-danger text-sm">
      <AlertCircleIcon className="size-4 shrink-0" aria-hidden />
      Task results didn't load.
      {onGoToFirstPage && (
        <Button variant="outline" size="xs" className="ml-auto" onPress={onGoToFirstPage}>
          Go to first page
        </Button>
      )}
    </div>
  );
}
