import type { ReactNode } from "react";
import { ErrorBoundary } from "react-error-boundary";

import ErrorScreen from "@/shared/components/errors/error-screen";

import { BRANCHES_LOAD_FAILED } from "@/entities/repository/ui/repository-branches-card/messages";

interface RepositoryBranchesCardBoundaryProps {
  children: ReactNode;
  // A failure caused by one row's data can only clear once a different row set arrives, so these
  // are the rows themselves rather than the inputs that asked for them.
  resetKeys: unknown[];
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
