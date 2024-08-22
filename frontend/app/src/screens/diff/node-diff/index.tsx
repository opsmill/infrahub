import { PROPOSED_CHANGES_OBJECT_THREAD_OBJECT } from "@/config/constants";
import useQuery from "@/hooks/useQuery";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { schemaState } from "@/state/atoms/schema.atom";
import { useAtomValue } from "jotai";
import { createContext } from "react";
import { useParams } from "react-router-dom";
import {
  diffActions,
  DiffFilter,
  ProposedChangesDiffSummary,
} from "../../proposed-changes/diff-summary";
import { getProposedChangesDiffTree } from "@/graphql/queries/proposed-changes/getProposedChangesDiffTree";
import { DiffNode } from "./node";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "@/config/qsp";
import NoDataFound from "@/screens/errors/no-data-found";
import { PcApproveButton } from "@/screens/proposed-changes/action-button/pc-approve-button";
import { PcMergeButton } from "@/screens/proposed-changes/action-button/pc-merge-button";
import { PcCloseButton } from "@/screens/proposed-changes/action-button/pc-close-button";

export const DiffContext = createContext({});

type NodeDiffProps = {
  filters: DiffFilter;
};

// Handle QSP to filter from the status
const buildFilters = (filters: DiffFilter, qsp?: String | null) => {
  const statusFilter = {
    ...filters?.status,
    includes: Array.from(
      // CONFLICT should not be part of the status filters
      new Set([...(filters?.status?.includes ?? []), qsp !== diffActions.CONFLICT && qsp])
    ).filter((value) => !!value),
  };

  return {
    ...filters,
    status: statusFilter,
  };
};

export const NodeDiff = ({ filters }: NodeDiffProps) => {
  const { "*": branchName, proposedChangeId } = useParams();
  const [qsp] = useQueryParam(QSP.STATUS, StringParam);
  const proposedChangesDetails = useAtomValue(proposedChangedState);
  const nodeSchemas = useAtomValue(schemaState);

  const branch = proposedChangesDetails?.source_branch?.value || branchName; // Used in proposed changes view and branch view

  const schemaData = nodeSchemas.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);

  const state = proposedChangesDetails?.state?.value;

  // Get filters merged with status filter
  const finalFilters = buildFilters(filters, qsp);

  const { loading, data } = useQuery(getProposedChangesDiffTree, {
    skip: !schemaData,
    variables: { branch, filters: finalFilters },
  });

  // Manually filter conflicts items since it's not available yet in the backend filters
  const nodes = data?.DiffTree?.nodes.filter((node) => {
    if (qsp === diffActions.CONFLICT) return node.contains_conflict;

    return node;
  });

  if (loading) {
    return <LoadingScreen message="Loading diff..." />;
  }

  return (
    <>
      <div className="flex items-center justify-between p-2 bg-custom-white">
        <ProposedChangesDiffSummary branch={branch} filters={filters} />

        {!branchName && (
          <div className="flex gap-2">
            <PcApproveButton
              size="sm"
              proposedChangeId={proposedChangeId!}
              approvers={
                proposedChangesDetails?.approved_by?.edges.map((edge: any) => edge.node) ?? []
              }
            />
            <PcMergeButton
              size="sm"
              sourceBranch={proposedChangesDetails?.source_branch?.value}
              proposedChangeId={proposedChangeId!}
              state={state}
            />
            <PcCloseButton size="sm" proposedChangeId={proposedChangeId!} state={state} />
          </div>
        )}
      </div>

      <div className="p-2.5 space-y-4">
        {nodes?.length ? (
          nodes.map((node) => (
            <DiffNode
              key={node.uuid}
              node={node}
              sourceBranch={data?.DiffTree?.base_branch}
              destinationBranch={data?.DiffTree?.diff_branch}
            />
          ))
        ) : (
          <NoDataFound message="No diff to display." />
        )}
      </div>
    </>
  );
};
