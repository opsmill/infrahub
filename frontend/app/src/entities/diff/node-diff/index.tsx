import { PROPOSED_CHANGES_OBJECT_THREAD_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { BRANCH_REBASE } from "@/entities/branches/api/rebaseBranch";
import { useUpdateDiffMutation } from "@/entities/diff/domain/update-diff.mutation";
import { DIFF_STATUS, DiffNode as DiffNodeType } from "@/entities/diff/node-diff/types";
import { DiffComputing } from "@/entities/diff/ui/diff-computing";
import { DiffEmpty } from "@/entities/diff/ui/diff-empty";
import { DiffNoFound } from "@/entities/diff/ui/diff-no-found";
import { DiffRefreshButton } from "@/entities/diff/ui/diff-refresh-button";
import DiffTree from "@/entities/diff/ui/diff-tree";
import { getProposedChangesDiffTree } from "@/entities/proposed-changes/api/getProposedChangesDiffTree";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { schemaState } from "@/entities/schema/stores/schema.atom";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import useQuery from "@/shared/api/graphql/useQuery";
import { Button } from "@/shared/components/buttons/button-primitive";
import { DateDisplay } from "@/shared/components/display/date-display";
import ErrorScreen from "@/shared/components/errors/error-screen";
import LoadingScreen from "@/shared/components/loading-screen";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { NetworkStatus } from "@apollo/client";
import { useAtomValue } from "jotai";
import { createContext, useState } from "react";
import { toast } from "react-toastify";
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
  const date = useAtomValue(datetimeAtom);
  const proposedChangesDetails = useAtomValue(proposedChangedState);
  const nodeSchemas = useAtomValue(schemaState);
  const [isLoadingUpdate, setIsLoadingUpdate] = useState(false);

  const branch = proposedChangesDetails?.source_branch?.value || branchName; // Used in proposed changes view and branch view

  const updateDiffMutation = useUpdateDiffMutation();

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

  const handleRefresh = async () => {
    setIsLoadingUpdate(true);
    try {
      await updateDiffMutation.mutateAsync(branch);

      await graphqlClient.refetchQueries({
        include: ["GET_PROPOSED_CHANGES_DIFF_TREE", "GET_PROPOSED_CHANGES_DIFF_SUMMARY"],
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Diff updated!" />);
    } catch (error: any) {
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={error?.message} />);
    }
    setIsLoadingUpdate(false);
  };

  const handleRebase = async () => {
    setIsLoadingUpdate(true);

    try {
      await graphqlClient.mutate({
        mutation: BRANCH_REBASE,
        variables: {
          name: branch,
        },
        context: {
          branch: branchName,
          date,
        },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Branch rebased!" />);

      await handleRefresh();
    } catch (error: any) {
      toast(<Alert type={ALERT_TYPES.ERROR} message={error?.message} />);
    }

    setIsLoadingUpdate(false);
  };

  const diffTreeData = (data || previousData)?.DiffTree;

  // When a proposed change is created, there is also a job that compute the diff that is triggered.
  // If DiffTree is null, it means that diff is still being computed.
  if (!diffTreeData) {
    return (
      <DiffComputing
        sourceBranch={proposedChangesDetails.source_branch?.value}
        destinationBranch={proposedChangesDetails.destination_branch?.value}
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
      <div className="flex items-center p-2 bg-custom-white border-b">
        <ProposedChangeDiffFilter branch={branch} filters={filters} />

        <div className="flex flex-1 items-center gap-2 justify-end pr-2">
          {isLoadingUpdate && <LoadingScreen size={22} hideText />}

          <div className="flex items-center">
            <div className="flex items-center text-xs mr-2">
              <span className="mr-1">Updated</span>
              <DateDisplay date={diffTreeData?.to_time} />
            </div>

            <DiffRefreshButton size="sm" variant="primary" branchName={branch} />
          </div>

          <Button
            size="sm"
            variant="primary-outline"
            onClick={handleRebase}
            disabled={isLoadingUpdate}
          >
            Rebase
          </Button>
        </div>
      </div>

      <div className="flex-grow grid grid-cols-4 overflow-hidden">
        <div className="p-4 col-span-1 overflow-auto border-r">
          <DiffTree nodes={nodes} className="w-full" />
        </div>

        <div className="space-y-4 p-4 col-start-2 col-end-5 overflow-auto bg-stone-100">
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
        </div>
      </div>
    </div>
  );
};
