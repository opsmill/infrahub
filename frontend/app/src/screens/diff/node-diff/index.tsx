import { PROPOSED_CHANGES_OBJECT_THREAD_OBJECT } from "@/config/constants";
import useQuery from "@/hooks/useQuery";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { schemaState } from "@/state/atoms/schema.atom";
import { useAtomValue } from "jotai";
import { createContext, useState } from "react";
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
import { Card } from "@/components/ui/card";
import DiffTree from "@/screens/diff/diff-tree";
import type { DiffNode as DiffNodeType } from "@/screens/diff/node-diff/types";
import { Button } from "@/components/buttons/button-primitive";
import { rebaseBranch } from "@/graphql/mutations/branches/rebaseBranch";
import { objectToString } from "@/utils/common";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { gql, useMutation } from "@apollo/client";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { DIFF_UPDATE } from "@/graphql/mutations/proposed-changes/diff/diff-update";
import { useAuth } from "@/hooks/useAuth";
import { DateDisplay } from "@/components/display/date-display";

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
  const auth = useAuth();
  const [qspStatus, setQspStatus] = useQueryParam(QSP.STATUS, StringParam);
  const date = useAtomValue(datetimeAtom);
  const proposedChangesDetails = useAtomValue(proposedChangedState);
  const nodeSchemas = useAtomValue(schemaState);
  const [isLoadingUpdate, setIsLoadingUpdate] = useState(false);

  const branch = proposedChangesDetails?.source_branch?.value || branchName; // Used in proposed changes view and branch view

  const [scheduleDiffTreeUpdate] = useMutation(DIFF_UPDATE, {
    variables: { branchName: branch, wait: true },
  });

  const schemaData = nodeSchemas.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);

  // Get filters merged with status filter
  const finalFilters = buildFilters(filters, qspStatus);

  const { loading, data } = useQuery(getProposedChangesDiffTree, {
    skip: !schemaData,
    variables: { branch, filters: finalFilters },
  });

  // Manually filter conflicts items since it's not available yet in the backend filters
  const nodes: Array<DiffNodeType> =
    data?.DiffTree?.nodes.filter((node: DiffNodeType) => {
      if (qspStatus === diffActions.CONFLICT) return node.contains_conflict;

      return true;
    }) ?? [];

  const handleRefresh = async () => {
    setIsLoadingUpdate(true);
    try {
      await scheduleDiffTreeUpdate();

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
      const options = {
        name: branch,
      };

      const mutationString = rebaseBranch({ data: objectToString(options) });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
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

  return (
    <div className="h-full overflow-hidden flex flex-col">
      <div className="flex items-center p-2 bg-custom-white divide-x">
        <div className="mr-2">
          <ProposedChangesDiffSummary branch={branch} filters={filters} />
        </div>

        <div className="flex flex-1 pl-2 items-center justify-between">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setQspStatus(undefined)}
            isLoading={loading}>
            Reset Filter
          </Button>

          <div className="flex items-center gap-2 pr-2">
            {isLoadingUpdate && <LoadingScreen size={22} hideText />}

            <div className="flex items-center">
              <div className="flex items-center text-xs mr-2">
                <span className="mr-1">Updated</span>
                <DateDisplay date={data?.DiffTree?.to_time} />
              </div>

              <Button
                size="sm"
                variant="primary"
                onClick={handleRefresh}
                disabled={!auth?.permissions?.write || isLoadingUpdate}>
                Refresh diff
              </Button>
            </div>

            <Button
              size="sm"
              variant="primary-outline"
              onClick={handleRebase}
              disabled={isLoadingUpdate}>
              Rebase
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-grow grid grid-cols-4 overflow-hidden">
        <Card className="col-span-1 my-2.5 ml-2.5 overflow-auto">
          <DiffTree
            nodes={nodes}
            className="p-2 w-full"
            loading={loading}
            emptyMessage="No tree view available for the diff."
          />
        </Card>

        <div className="space-y-4 p-2.5 col-start-2 col-end-5 overflow-auto">
          {loading && <LoadingScreen message="Loading diff..." />}

          {!loading && !nodes.length && qspStatus && (
            <div className="flex flex-col items-center justify-center">
              <NoDataFound
                message={`No diff matches the status: ${qspStatus}. Please adjust your filter settings.`}
              />
            </div>
          )}

          {!loading && !nodes.length && !qspStatus && (
            <div className="flex flex-col items-center justify-center">
              <NoDataFound message="No diff to display. Try to manually load the latest changes." />
              <Button
                variant="primary-outline"
                onClick={handleRefresh}
                isLoading={isLoadingUpdate}
                disabled={!auth?.permissions?.write || isLoadingUpdate}>
                {isLoadingUpdate ? "Refreshing diff..." : "Refresh diff"}
              </Button>
            </div>
          )}

          {!loading &&
            !!nodes.length &&
            nodes.map((node) => (
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
