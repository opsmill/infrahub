import { DEFAULT_BRANCH_NAME, PROPOSED_CHANGES_OBJECT_THREAD_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { DIFF_STATUS, DiffNode as DiffNodeType } from "@/entities/diff/node-diff/types";
import { DiffComputing } from "@/entities/diff/ui/diff-computing";
import { DiffEmpty } from "@/entities/diff/ui/diff-empty";
import { DiffNoFound } from "@/entities/diff/ui/diff-no-found";
import { DiffRebaseButton } from "@/entities/diff/ui/diff-rebase-button";
import { DiffRefreshButton } from "@/entities/diff/ui/diff-refresh-button";
import DiffTree from "@/entities/diff/ui/diff-tree";
import { getProposedChangesDiffTree } from "@/entities/proposed-changes/api/getProposedChangesDiffTree";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { schemaState } from "@/entities/schema/stores/schema.atom";
import useQuery from "@/shared/api/graphql/useQuery";
import { DateDisplay } from "@/shared/components/display/date-display";
import ErrorScreen from "@/shared/components/errors/error-screen";
import LoadingScreen from "@/shared/components/loading-screen";
import { NetworkStatus } from "@apollo/client";
import { useAtomValue } from "jotai";
import { createContext } from "react";
import { StringParam, useQueryParam } from "use-query-params";
import { DiffFilter, ProposedChangeDiffFilter } from "../../proposed-changes/ui/diff-filter";
import { DiffNode } from "./node";

export const DiffContext = createContext({});

type NodeDiffProps = {
  filters: DiffFilter;
  branchName: string;
};

// Handle QSP to filter from the status
const buildFilters = (filters: DiffFilter, qsp?: string | null) => {
  const statusFilter = {
    ...filters?.status,
    includes: Array.from(
      // CONFLICT should not be part of the status filters
      new Set([...(filters?.status?.includes ?? []), qsp !== DIFF_STATUS.CONFLICT && qsp])
    ).filter((value) => !!value),
  };

  return {
    ...filters,
    status: statusFilter,
  };
};

export const NodeDiff = ({ branchName, filters }: NodeDiffProps) => {
  const [qspStatus] = useQueryParam(QSP.STATUS, StringParam);
  const proposedChangesDetails = useAtomValue(proposedChangedState);
  const nodeSchemas = useAtomValue(schemaState);

  const branch = proposedChangesDetails?.source_branch?.value || branchName; // Used in proposed changes view and branch view

  const schemaData = nodeSchemas.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);

  // Get filters merged with status filter
  const finalFilters = buildFilters(filters, qspStatus);

  const { networkStatus, data, previousData, error } = useQuery(getProposedChangesDiffTree, {
    skip: !schemaData,
    variables: { branch, filters: finalFilters },
    notifyOnNetworkStatusChange: true,
  });

  if (networkStatus === NetworkStatus.loading) return <LoadingScreen message="Loading diff..." />;

  if (error) {
    return <ErrorScreen message={error?.message} className="max-w-lg m-auto" />;
  }

  const diffTreeData = (data || previousData)?.DiffTree;

  // When a proposed change is created, there is also a job that compute the diff that is triggered.
  // If DiffTree is null, it means that diff is still being computed.
  if (!diffTreeData) {
    return (
      <DiffComputing
        sourceBranch={branch}
        destinationBranch={proposedChangesDetails.destination_branch?.value ?? DEFAULT_BRANCH_NAME}
      />
    );
  }

  if (!qspStatus && diffTreeData.nodes.length === 0) {
    return <DiffEmpty branchName={branch} lastRefreshedAt={diffTreeData.to_time} />;
  }

  // Manually filter conflicts items since it's not available yet in the backend filters
  const nodes: Array<DiffNodeType> =
    diffTreeData.nodes.filter((node: DiffNodeType) => {
      if (qspStatus === DIFF_STATUS.CONFLICT) return node.contains_conflict;

      return true;
    }) ?? [];

  return (
    <div className="h-full overflow-hidden flex flex-col">
      <header className="flex items-center px-4 py-2 border-b gap-2">
        <ProposedChangeDiffFilter branch={branch} filters={filters} />
        <span className="text-xs inline-flex gap-1 ml-auto">
          Updated <DateDisplay date={diffTreeData?.to_time} />
        </span>
        <DiffRefreshButton size="sm" variant="primary" branchName={branch} />
        <DiffRebaseButton branchName={branch} />
      </header>

      <div className="flex-grow grid grid-cols-4 overflow-hidden">
        <nav className="p-4 col-span-1 overflow-auto border-r">
          <DiffTree nodes={nodes} className="w-full" />
        </nav>

        <main className="space-y-4 p-4 col-start-2 col-end-5 overflow-auto bg-stone-100">
          {nodes.length ? (
            nodes
              .filter(({ status }) => status !== "UNCHANGED")
              .map((node) => (
                <DiffNode
                  key={node.uuid}
                  node={node}
                  sourceBranch={diffTreeData?.base_branch}
                  destinationBranch={diffTreeData?.diff_branch}
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
