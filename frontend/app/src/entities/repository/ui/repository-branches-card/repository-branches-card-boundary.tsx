import type { ReactNode } from "react";
import { ErrorBoundary } from "react-error-boundary";

import ErrorScreen from "@/shared/components/errors/error-screen";

import { BRANCHES_LOAD_FAILED } from "@/entities/repository/ui/repository-branches-card/messages";

interface RepositoryBranchesCardBoundaryProps {
  children: ReactNode;
}

// Without a card-scoped boundary a render-time failure in a row reaches the router's boundary and
// blanks the whole repository page, taking the details cards with it.
export function RepositoryBranchesCardBoundary({ children }: RepositoryBranchesCardBoundaryProps) {
  return (
    <ErrorBoundary
      fallbackRender={() => (
        <ErrorScreen className="flex-none py-12" message={BRANCHES_LOAD_FAILED} />
      )}
    >
      {children}
    </ErrorBoundary>
  );
}
