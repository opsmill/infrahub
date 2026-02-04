import { useAtomValue } from "jotai";
import { useQueryState } from "nuqs";
import { createContext, useEffect } from "react";

import { DateDisplay } from "@/shared/components/display/date-display";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { DEFAULT_BRANCH_NAME } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import type { GetDiffSummaryParams } from "@/entities/diff/domain/get-diff-summary";
import { useDiffTreeInfiniteQuery } from "@/entities/diff/domain/get-diff-tree";
import { DiffNode } from "@/entities/diff/node-diff/node";
import { DIFF_STATUS, type DiffNode as DiffNodeType } from "@/entities/diff/node-diff/types";
import { buildFilters } from "@/entities/diff/node-diff/utils";
import { DiffComputing } from "@/entities/diff/ui/diff-computing";
import { DiffEmpty } from "@/entities/diff/ui/diff-empty";
import { DiffNoFound } from "@/entities/diff/ui/diff-no-found";
import { DiffRebaseButton } from "@/entities/diff/ui/diff-rebase-button";
import { DiffRefreshButton } from "@/entities/diff/ui/diff-refresh-button";
import DiffTree from "@/entities/diff/ui/diff-tree";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { DiffFilter } from "@/entities/proposed-changes/ui/diff-filter";

export const DiffContext = createContext({});

type NodeDiffProps = GetDiffSummaryParams;

export const NodeDiff = ({ branch, filters }: NodeDiffProps) => {
  const [qspStatus] = useQueryState(QSP.STATUS);
  const proposedChangesDetails = useAtomValue(proposedChangedState);

  // When branch prop is provided, we're in branch diff view - use only the branch prop
  // When no branch prop, we're in proposed change view - use source_branch from proposedChangesDetails
  const branchName: string = branch || proposedChangesDetails?.source_branch?.value;

  // Get filters merged with status filter
  const finalFilters = buildFilters(filters, qspStatus);

  const { data, isPending, error, hasNextPage, fetchNextPage, isFetchingNextPage } =
    useDiffTreeInfiniteQuery({
      branchName,
      filters: finalFilters,
      // Only include proposedChangeId when in proposed change view (no branch prop passed)
      proposedChangeId: branch ? undefined : proposedChangesDetails?.id,
    });

  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <ErrorScreen message={error?.message} className="m-auto max-w-lg" />;
  }

  const firstPageNodes = data.pages[0];

  // When a proposed change is created, there is also a job that compute the diff that is triggered.
  // If DiffTree is null, it means that diff is still being computed.
  if (!firstPageNodes) {
    return (
      <DiffComputing
        sourceBranch={branchName}
        destinationBranch={proposedChangesDetails.destination_branch?.value ?? DEFAULT_BRANCH_NAME}
      />
    );
  }

  if (!qspStatus && firstPageNodes.nodes?.length === 0) {
    return <DiffEmpty branchName={branchName} lastRefreshedAt={firstPageNodes.to_time} />;
  }

  const nodes =
    data.pages
      .flatMap((page) => page?.nodes)
      .flatMap((node) => {
        if (!node || node.status === "UNCHANGED") return [];
        // Manually filter conflicts items since it's not available yet in the backend filters
        if (qspStatus === DIFF_STATUS.CONFLICT && !node.contains_conflict) return [];
        return node as unknown as DiffNodeType;
      }) ?? [];

  return (
    <div className="flex h-[calc(100vh-14rem)] flex-col overflow-hidden">
      <header className="flex items-center gap-2 border-gray-200 border-b px-4 py-2">
        <DiffFilter branch={branchName} filters={filters} />
        <span className="ml-auto inline-flex gap-1 text-xs">
          Updated <DateDisplay date={firstPageNodes?.to_time} />
        </span>
        <DiffRefreshButton size="sm" variant="primary" branchName={branchName} />
        <DiffRebaseButton branchName={branchName} />
      </header>

      <div className="grid grow grid-cols-4 overflow-hidden">
        <nav className="col-span-1 overflow-auto border-gray-200 border-r p-4">
          <DiffTree nodes={nodes} className="w-full" />
        </nav>

        <main className="col-start-2 col-end-5 space-y-4 overflow-auto bg-stone-100 p-4">
          {nodes.length ? (
            nodes.map((node) => (
              <DiffNode
                key={node.uuid}
                node={node}
                sourceBranch={firstPageNodes?.base_branch}
                destinationBranch={firstPageNodes?.diff_branch}
              />
            ))
          ) : (
            <DiffNoFound diffStatus={qspStatus as string} />
          )}
        </main>
      </div>
    </div>
  );
};
