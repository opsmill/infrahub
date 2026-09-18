import type { ReactNode } from "react";
import { ErrorBoundary } from "react-error-boundary";

import ErrorScreen from "@/shared/components/errors/error-screen";

import { BRANCHES_LOAD_FAILED } from "@/entities/repository/ui/repository-branches-card/messages";

interface RepositoryBranchesCardBoundaryProps {
  children: ReactNode;
  // The query inputs behind the rendered rows: a failure caused by one row's data can only clear
  // once a different row set is asked for, so re-rendering the same page must stay failed.
  resetKeys: Array<string | number>;
}

export function RepositoryBranchesCardBoundary({
  children,
  resetKeys,
}: RepositoryBranchesCardBoundaryProps) {
  return (
    <ErrorBoundary
      fallbackRender={() => (
        <ErrorScreen className="flex-none py-12" message={BRANCHES_LOAD_FAILED} />
      )}
      resetKeys={resetKeys}
    >
      {children}
    </ErrorBoundary>
  );
}
