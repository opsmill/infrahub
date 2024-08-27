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
import { Card } from "@/components/ui/card";
import DiffTree from "@/screens/diff/diff-tree";
import type { DiffNode as DiffNodeType } from "@/screens/diff/node-diff/types";
import { Button } from "@/components/buttons/button-primitive";

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
  const [qspStatus, setQspStatus] = useQueryParam(QSP.STATUS, StringParam);
  const proposedChangesDetails = useAtomValue(proposedChangedState);
  const nodeSchemas = useAtomValue(schemaState);

  const branch = proposedChangesDetails?.source_branch?.value || branchName; // Used in proposed changes view and branch view

  const schemaData = nodeSchemas.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);

  // Get filters merged with status filter
  const finalFilters = buildFilters(filters, qspStatus);

  const { loading, data } = useQuery(getProposedChangesDiffTree, {
    skip: !schemaData,
    variables: { branch, filters: finalFilters },
  });

  // Manually filter conflicts items since it's not available yet in the backend filters
  const nodes: Array<DiffNodeType> = data?.DiffTree?.nodes.filter((node: DiffNodeType) => {
    if (qspStatus === diffActions.CONFLICT) return node.contains_conflict;

    return true;
  });

  if (loading) {
    return <LoadingScreen message="Loading diff..." />;
  }

  if (!nodes?.length) {
    if (qspStatus) {
      return (
        <div className="flex flex-col items-center justify-center">
          <NoDataFound
            message={`No diff matches the status: ${qspStatus}. Please adjust your filter settings.`}
          />
          <Button size="sm" variant="outline" onClick={() => setQspStatus(undefined)}>
            Reset Filter
          </Button>
        </div>
      );
    }

    return (
      <div className="flex flex-col items-center justify-center">
        <NoDataFound message="No diff to display. Try to manually load the latest changes." />
        <PcDiffUpdateButton size="sm" sourceBranch={proposedChangesDetails?.source_branch?.value} />
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden flex flex-col">
      <div className="flex items-center p-2 bg-custom-white divide-x">
        <div className="mr-2">
          <ProposedChangesDiffSummary branch={branch} filters={filters} />
        </div>

        {!!nodes?.length && (
          <div className="pl-2 ">
            <PcDiffUpdateButton
              size="sm"
              time={data?.DiffTree?.to_time}
              sourceBranch={proposedChangesDetails?.source_branch?.value}
            />
          </div>
        )}
      </div>

      <div className="flex-grow grid grid-cols-4 overflow-hidden">
        <Card className="col-span-1 my-2.5 ml-2.5 overflow-auto">
          <DiffTree nodes={nodes} className="p-2 w-full" />
        </Card>

        <div className="space-y-4 p-2.5 col-start-2 col-end-5 overflow-auto">
          {nodes.map((node) => (
            <DiffNode
              key={node.uuid}
              node={node}
              sourceBranch={data?.DiffTree?.base_branch}
              destinationBranch={data?.DiffTree?.diff_branch}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
