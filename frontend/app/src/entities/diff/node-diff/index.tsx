import { useAtomValue } from "jotai";
import { createContext, useEffect } from "react";
import { StringParam, useQueryParam } from "use-query-params";

import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { QSP } from "@/config/qsp";

import { DateDisplay } from "@/shared/components/display/date-display";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useDiffTreeInfiniteQuery } from "@/entities/diff/domain/get-diff-tree";
import { DIFF_STATUS, DiffNode as DiffNodeType } from "@/entities/diff/node-diff/types";
import { buildFilters } from "@/entities/diff/node-diff/utils";
import { DiffComputing } from "@/entities/diff/ui/diff-computing";
import { DiffEmpty } from "@/entities/diff/ui/diff-empty";
import { DiffNoFound } from "@/entities/diff/ui/diff-no-found";
import { DiffRebaseButton } from "@/entities/diff/ui/diff-rebase-button";
import { DiffRefreshButton } from "@/entities/diff/ui/diff-refresh-button";
import DiffTree from "@/entities/diff/ui/diff-tree";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";

import { DiffFilter, ProposedChangeDiffFilter } from "../../proposed-changes/ui/diff-filter";
import { DiffNode } from "./node";

export const DiffContext = createContext({});

type NodeDiffProps = {
  filters: DiffFilter;
  branchName: string;
};

export const NodeDiff = ({ branchName, filters }: NodeDiffProps) => {
  const [qspStatus] = useQueryParam(QSP.STATUS, StringParam);
  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const branch = proposedChangesDetails?.source_branch?.value || branchName; // Used in proposed changes view and branch view

  // Get filters merged with status filter
  const finalFilters = buildFilters(filters, qspStatus);

  const { data, isPending, error, hasNextPage, fetchNextPage, isFetchingNextPage } =
    useDiffTreeInfiniteQuery({
      branchName: branch,
      filters: finalFilters,
    });

  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [hasNextPage, isFetchingNextPage]);

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
        sourceBranch={branch}
        destinationBranch={proposedChangesDetails.destination_branch?.value ?? DEFAULT_BRANCH_NAME}
      />
    );
  }

  if (!qspStatus && firstPageNodes.nodes?.length === 0) {
    return <DiffEmpty branchName={branch} lastRefreshedAt={firstPageNodes.to_time} />;
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
        <ProposedChangeDiffFilter branch={branch} filters={filters} />
        <span className="ml-auto inline-flex gap-1 text-xs">
          Updated <DateDisplay date={firstPageNodes?.to_time} />
        </span>
        <DiffRefreshButton size="sm" variant="primary" branchName={branch} />
        <DiffRebaseButton branchName={branch} />
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
