import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { CONFIG } from "@/config/config";
import { PROPOSED_CHANGES_OBJECT, PROPOSED_CHANGES_OBJECT_THREAD_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { getThreadsAndChecks } from "@/graphql/queries/proposed-changes/getThreadsAndChecks";
import useQuery from "@/hooks/useQuery";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { schemaState } from "@/state/atoms/schema.atom";
import { fetchUrl, getUrlWithQsp } from "@/utils/fetch";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import {
  createContext,
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useState,
} from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { DataDiffNode, tDataDiffNode } from "./data-diff-node";
import { ProposedChangesData } from "../proposed-changes/diff-summary";
import { Button } from "@/components/buttons/button-primitive";
import { useAuth } from "@/hooks/useAuth";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { stringifyWithoutQuotes } from "@/utils/string";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { datetimeAtom } from "@/state/atoms/time.atom";

type tDiffContext = {
  refetch?: Function;
  node?: tDataDiffNode;
  currentBranch?: string;
  checksDictionnary?: any;
};

export const DiffContext = createContext<tDiffContext>({});

const constructChecksDictionnary = (checks: any[]) => {
  // Flatten all the checks from all validators
  const totalChecks = checks
    ?.map((validator: any) => validator?.edges?.map((edge: any) => edge?.node))
    .reduce((acc, elem) => [...acc, ...elem], []);

  // Construct with path as key and check as value
  const dictionnary = totalChecks?.reduce((acc: any, elem: any) => {
    // For each path, get { path1: [check1, check2], path2: [check3], ... }
    const paths = elem?.conflicts?.value?.reduce((acc2: any, conflict: any) => {
      return {
        ...acc2,
        [conflict.path]: [...(acc[conflict.path] || []), elem],
      };
    }, {});

    return {
      ...acc,
      ...paths,
    };
  }, {});

  return dictionnary;
};

export const DataDiff = forwardRef((props, ref) => {
  const { branchName, proposedchange } = useParams();
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);
  const date = useAtomValue(datetimeAtom);
  const proposedChangesDetails = useAtomValue(proposedChangedState);
  const schemaList = useAtomValue(schemaState);
  const [diff, setDiff] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingApprove, setIsLoadingApprove] = useState(false);
  const [isLoadingMerge, setIsLoadingMerge] = useState(false);
  const [isLoadingClose, setIsLoadingClose] = useState(false);
  const auth = useAuth();

  const branch = proposedChangesDetails?.source_branch?.value || branchName; // Used in proposed changes view and branch view

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);

  const state = proposedChangesDetails?.state?.value;
  const approverId = auth?.data?.sub;
  const approvers = proposedChangesDetails?.approved_by?.edges.map((edge: any) => edge.node) ?? [];
  const oldApproversId = approvers.map((a: any) => a.id);

  const queryString = schemaData
    ? getThreadsAndChecks({
        id: proposedchange,
        kind: schemaData.kind,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { data, refetch } = useQuery(query, { skip: !schemaData });

  // Get the comments count per object path like { [path]: [count] }, and include all sub path for each object
  const objectComments = data?.[PROPOSED_CHANGES_OBJECT_THREAD_OBJECT]?.edges
    .map((edge: any) => edge.node)
    .reduce((acc: any, node: any) => {
      const objectPathResult = node?.object_path?.value?.match(/^\w+\/(\w|-)+/g);

      const objectPath = objectPathResult && objectPathResult[0];

      if (!objectPath) {
        return;
      }

      return {
        ...acc,
        // Count all comments for this object (will include comments on sub nodes)
        [objectPath]: (acc[objectPath] ?? 0) + (node?.comments?.count ?? 0),
      };
    }, {});

  const checks = data?.CoreValidator?.edges?.map((edge: any) => edge?.node?.checks);

  const checksDictionnary = constructChecksDictionnary(checks);

  const fetchDiffDetails = useCallback(async () => {
    if (!branch) return;

    setIsLoading(true);

    const url = CONFIG.DATA_DIFF_URL(branch);

    const options: string[][] = [
      ["branch_only", "false"], // default will be branch only
      ["time_from", timeFrom ?? ""],
      ["time_to", timeTo ?? ""],
    ].filter(([, v]) => v !== undefined && v !== "");

    const urlWithQsp = getUrlWithQsp(url, options);

    try {
      const diffDetails = await fetchUrl(urlWithQsp);

      setDiff(diffDetails.diffs ?? []);
    } catch (err) {
      console.error("Error when fethcing branches: ", err);

      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading branch diff" />);
    }

    setIsLoading(false);
  }, [branch, timeFrom, timeTo]);

  const handleApprove = async () => {
    if (!approverId) {
      return;
    }

    setIsLoadingApprove(true);

    const newApproverId = approverId;
    const newApproversId = Array.from(new Set([...oldApproversId, newApproverId]));
    const newApprovers = newApproversId.map((id: string) => ({ id }));

    const data = {
      approved_by: newApprovers,
    };

    try {
      const mutationString = updateObjectWithId({
        kind: PROPOSED_CHANGES_OBJECT,
        data: stringifyWithoutQuotes({
          id: proposedchange,
          ...data,
        }),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: { branch: branch?.name, date },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Proposed change approved" />);

      setIsLoadingApprove(false);

      return;
    } catch (e) {
      console.error("Something went wrong while updating the object:", e);

      return;
    }
  };

  const handleMerge = async () => {
    if (!proposedChangesDetails?.source_branch?.value) return;

    try {
      setIsLoadingMerge(true);

      const stateData = {
        state: {
          value: "merged",
        },
      };

      const stateMutationString = updateObjectWithId({
        kind: PROPOSED_CHANGES_OBJECT,
        data: stringifyWithoutQuotes({
          id: proposedchange,
          ...stateData,
        }),
      });

      const stateMutation = gql`
        ${stateMutationString}
      `;

      await graphqlClient.mutate({
        mutation: stateMutation,
        context: { branch: branch?.name, date },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Proposed changes merged successfully!"} />);
    } catch (error: any) {
      console.log("error: ", error);

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={"An error occurred while merging the proposed changes"}
        />
      );
    }

    setIsLoadingMerge(false);
  };

  const handleClose = async () => {
    setIsLoadingClose(true);

    const newState = state === "closed" ? "open" : "closed";

    const data = {
      state: {
        value: newState,
      },
    };

    try {
      const mutationString = updateObjectWithId({
        kind: PROPOSED_CHANGES_OBJECT,
        data: stringifyWithoutQuotes({
          id: proposedchange,
          ...data,
        }),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: { branch: branch?.name, date },
      });

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`Proposed change ${state === "closed" ? "opened" : "closed"}`}
        />
      );

      setIsLoadingClose(false);

      return;
    } catch (e) {
      console.error("Something went wrong while updating the object:", e);

      setIsLoadingClose(false);

      return;
    }
  };

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch: fetchDiffDetails }));

  useEffect(() => {
    fetchDiffDetails();
  }, [fetchDiffDetails]);

  const renderNode = (node: any, index: number) => {
    // Provide threads and comments counts to display in the top level node
    const commentsCount = objectComments && objectComments[node?.path];

    const currentBranch =
      branch ?? branchName ?? proposedChangesDetails?.source_branch?.value ?? "main";

    const context = {
      currentBranch,
      // Provides refetch function to update count on comment
      refetch,
      // Provides full node information
      node,
      // Provides all the checks results
      checksDictionnary,
    };

    return (
      <DiffContext.Provider key={index} value={context}>
        <DataDiffNode node={node} commentsCount={commentsCount} />
      </DiffContext.Provider>
    );
  };

  return (
    <>
      <div className="flex items-center justify-between p-2 bg-custom-white">
        <ProposedChangesData branch={branch} />

        <div className="flex gap-2">
          <Button
            variant={"outline"}
            onClick={handleApprove}
            isLoading={isLoadingApprove}
            disabled={oldApproversId.includes(approverId)}>
            Approve
          </Button>
          <Button
            variant={"active"}
            onClick={handleMerge}
            isLoading={isLoadingMerge}
            disabled={!auth?.permissions?.write || state === "closed" || state === "merged"}>
            Merge
          </Button>
          <Button
            variant={"danger"}
            onClick={handleClose}
            isLoading={isLoadingClose}
            disabled={!auth?.permissions?.write || state === "merged"}>
            {state === "closed" ? "Re-open" : "Close"}
          </Button>
        </div>
      </div>

      {isLoading ? (
        <LoadingScreen />
      ) : (
        <div className="text-xs" data-cy="data-diff">
          {diff?.map(renderNode)}
        </div>
      )}
    </>
  );
});
