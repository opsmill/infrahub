import { PROPOSED_CHANGES_OBJECT_THREAD_OBJECT } from "@/config/constants";
import useQuery from "@/hooks/useQuery";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { schemaState } from "@/state/atoms/schema.atom";
import { useAtomValue } from "jotai";
import { createContext, useState } from "react";
import {
  diffActions,
  DiffFilter,
  ProposedChangeDiffFilter,
} from "../../proposed-changes/diff-filter";
import { getProposedChangesDiffTree } from "@/graphql/queries/proposed-changes/getProposedChangesDiffTree";
import { DiffNode } from "./node";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "@/config/qsp";
import { Card } from "@/components/ui/card";
import DiffTree from "@/screens/diff/diff-tree";
import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { rebaseBranch } from "@/graphql/mutations/branches/rebaseBranch";
import { classNames, objectToString } from "@/utils/common";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { gql, useMutation } from "@apollo/client";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { DIFF_UPDATE } from "@/graphql/mutations/proposed-changes/diff/diff-update";
import { useAuth } from "@/hooks/useAuth";
import { DateDisplay } from "@/components/display/date-display";
import { Icon } from "@iconify-icon/react";
import type { DiffNode as DiffNodeType } from "@/screens/diff/node-diff/types";
import { formatFullDate, formatRelativeTimeFromNow } from "@/utils/date";
import { Tooltip } from "@/components/ui/tooltip";
import { DiffBadge } from "@/screens/diff/node-diff/utils";
import { Badge } from "@/components/ui/badge";

export const DiffContext = createContext({});

type NodeDiffProps = {
  filters: DiffFilter;
  branchName: string;
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

export const NodeDiff = ({ branchName, filters }: NodeDiffProps) => {
  const auth = useAuth();
  const [qspStatus] = useQueryParam(QSP.STATUS, StringParam);
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

  const { loading, called, data, previousData } = useQuery(getProposedChangesDiffTree, {
    skip: !schemaData,
    variables: { branch, filters: finalFilters },
    notifyOnNetworkStatusChange: true,
  });

  if (!called && loading) return <LoadingScreen message="Loading diff..." />;

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

  const diffTreeData = (data || previousData)?.DiffTree;

  // When a proposed change is created, there is also a job that compute the diff that is triggered.
  // If DiffTree is null, it means that diff is still being computed.
  if (!diffTreeData) {
    return (
      <div className="flex flex-col items-center mt-10 gap-5">
        <LoadingScreen hideText />

        <h1 className="font-semibold">
          We are computing the diff between{" "}
          <Badge variant="blue">
            <Icon icon={"mdi:layers-triple"} className="mr-1" />{" "}
            {proposedChangesDetails.source_branch?.value}
          </Badge>{" "}
          and{" "}
          <Badge variant="green">
            <Icon icon={"mdi:layers-triple"} className="mr-1" />{" "}
            {proposedChangesDetails.destination_branch?.value}
          </Badge>
        </h1>

        <div className="text-center">
          <p>This process may take a few seconds to a few minutes.</p>
          <p>Once completed, you&apos;ll be able to view the detailed changes.</p>
        </div>

        <RefreshButton
          onClick={handleRefresh}
          disabled={!auth?.permissions?.write || isLoadingUpdate}
          isLoading={isLoadingUpdate}
        />
      </div>
    );
  }

  if (!qspStatus && diffTreeData.nodes.length === 0) {
    return (
      <div className="flex flex-col items-center mt-10 gap-5">
        <div className="p-3 rounded-full bg-white inline-flex">
          <Icon icon="mdi:circle-off-outline" className="text-2xl text-custom-blue-800" />
        </div>

        <h1 className="font-semibold text-lg">No changes detected</h1>
        <div className="text-center">
          <p>
            The last comparison was made{" "}
            <Tooltip enabled content={formatFullDate(diffTreeData.to_time)}>
              <span className="font-semibold">
                {formatRelativeTimeFromNow(diffTreeData.to_time)}
              </span>
            </Tooltip>
            .
          </p>
          <p>If you have made any changes, please refresh the diff:</p>
        </div>

        <RefreshButton
          onClick={handleRefresh}
          disabled={!auth?.permissions?.write || isLoadingUpdate}
          isLoading={isLoadingUpdate}
        />
      </div>
    );
  }

  // Manually filter conflicts items since it's not available yet in the backend filters
  const nodes: Array<DiffNodeType> =
    diffTreeData.nodes.filter((node: DiffNodeType) => {
      if (qspStatus === diffActions.CONFLICT) return node.contains_conflict;

      return true;
    }) ?? [];

  return (
    <div className="h-full overflow-hidden flex flex-col">
      <div className="flex items-center p-2 bg-custom-white">
        <ProposedChangeDiffFilter branch={branch} filters={filters} />

        <div className="flex flex-1 items-center gap-2 justify-end pr-2">
          {isLoadingUpdate && <LoadingScreen size={22} hideText />}

          <div className="flex items-center">
            <div className="flex items-center text-xs mr-2">
              <span className="mr-1">Updated</span>
              <DateDisplay date={diffTreeData?.to_time} />
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

      <div className="flex-grow grid grid-cols-4 overflow-hidden">
        <Card className="col-span-1 my-2.5 ml-2.5 overflow-auto">
          <DiffTree nodes={nodes} className="p-2 w-full" />
        </Card>

        <div className="space-y-4 p-2.5 col-start-2 col-end-5 overflow-auto">
          {nodes.length === 0 && qspStatus && (
            <div className="flex flex-col items-center mt-10 gap-5">
              <div className="p-3 rounded-full bg-white inline-flex">
                <Icon icon="mdi:circle-off-outline" className="text-2xl text-custom-blue-800" />
              </div>

              <div className="text-center">
                <h1 className="font-semibold">
                  No matches found for the status <DiffBadge status={qspStatus} />
                </h1>
                <p>Try adjusting the filter settings to include more results.</p>
              </div>
            </div>
          )}

          {!!nodes.length &&
            nodes
              .filter(({ status }) => status !== "UNCHANGED")
              .map((node) => (
                <DiffNode
                  key={node.uuid}
                  node={node}
                  sourceBranch={diffTreeData?.base_branch}
                  destinationBranch={diffTreeData?.diff_branch}
                />
              ))}
        </div>
      </div>
    </div>
  );
};

const RefreshButton = ({ isLoading, ...props }: ButtonProps) => {
  return (
    <Button variant="primary-outline" {...props}>
      <Icon icon="mdi:reload" className={classNames("mr-1", isLoading && "animate-spin")} />
      {isLoading ? "Refreshing..." : "Refresh"}
    </Button>
  );
};
