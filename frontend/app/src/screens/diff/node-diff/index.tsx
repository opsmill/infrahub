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
import { PcDiffUpdateButton } from "@/screens/proposed-changes/action-button/pc-diff-update-button";

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
  const { "*": branchName } = useParams();
  const [qsp] = useQueryParam(QSP.STATUS, StringParam);
  const proposedChangesDetails = useAtomValue(proposedChangedState);
  const nodeSchemas = useAtomValue(schemaState);

  const branch = proposedChangesDetails?.source_branch?.value || branchName; // Used in proposed changes view and branch view

  const schemaData = nodeSchemas.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);

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
      <div className="flex items-center p-2 bg-custom-white">
        <div className="mr-2">
          <ProposedChangesDiffSummary branch={branch} filters={filters} />
        </div>

        {!!nodes?.length && (
          <PcDiffUpdateButton
            size="sm"
            time={data?.DiffTree?.to_time}
            sourceBranch={proposedChangesDetails?.source_branch?.value}
          />
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
          <div className="flex flex-col items-center justify-center">
            <NoDataFound message="No diff to display. Try to manually load the latest changes." />
            <PcDiffUpdateButton
              size="sm"
              sourceBranch={proposedChangesDetails?.source_branch?.value}
            />
          </div>
        )}
      </div>
    </>
  );
};
