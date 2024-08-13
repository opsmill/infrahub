import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { PROPOSED_CHANGES_OBJECT, PROPOSED_CHANGES_OBJECT_THREAD_OBJECT } from "@/config/constants";
import useQuery from "@/hooks/useQuery";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { schemaState } from "@/state/atoms/schema.atom";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { createContext, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { ProposedChangesDiffSummary } from "../../proposed-changes/diff-summary";
import { Button } from "@/components/buttons/button-primitive";
import { useAuth } from "@/hooks/useAuth";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { stringifyWithoutQuotes } from "@/utils/string";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@iconify-icon/react";
import { getProposedChangesDiffTree } from "@/graphql/queries/proposed-changes/getProposedChangesDiffTree";
import { DiffNode } from "./node";

export const DiffContext = createContext({});

export const DataDiff = () => {
  const { "*": branchName, proposedchange } = useParams();
  const date = useAtomValue(datetimeAtom);
  const proposedChangesDetails = useAtomValue(proposedChangedState);
  const schemaList = useAtomValue(schemaState);
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

  const query = gql`
    ${getProposedChangesDiffTree}
  `;

  const { loading, data } = useQuery(query, {
    skip: !schemaData,
    variables: { branch },
  });

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

      await graphqlClient.refetchQueries({ include: ["GET_PROPOSED_CHANGES"] });
    } catch (e) {
      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={"An error occurred while approving the proposed changes"}
        />
      );
    }

    setIsLoadingApprove(false);
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

      await graphqlClient.refetchQueries({ include: ["GET_PROPOSED_CHANGES"] });
    } catch (error: any) {
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

      await graphqlClient.refetchQueries({ include: ["GET_PROPOSED_CHANGES"] });
    } catch (e) {
      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={"An error occurred while closing the proposed changes"}
        />
      );
    }

    setIsLoadingClose(false);
  };

  const nodes = data?.DiffTree?.nodes
    ?.filter((node) => node.status !== "UNCHANGED")
    ?.filter((node) => node.__typename === "DiffNode");

  return (
    <>
      <div className="flex items-center justify-between p-2 bg-custom-white">
        <div className="flex gap-2">
          <div className="mr-4">
            <ProposedChangesDiffSummary branch={branch} />
          </div>

          <Badge variant={"green"}>
            <Icon icon="mdi:layers-triple" className="mr-1" />
            main
          </Badge>

          <Badge variant={"blue"}>
            <Icon icon="mdi:layers-triple" className="mr-1" />
            {branch}
          </Badge>
        </div>

        <div className="flex gap-2">
          <Button
            size={"sm"}
            variant={"outline"}
            onClick={handleApprove}
            isLoading={isLoadingApprove}
            disabled={oldApproversId.includes(approverId)}>
            Approve
          </Button>
          <Button
            size={"sm"}
            variant={"active"}
            onClick={handleMerge}
            isLoading={isLoadingMerge}
            disabled={!auth?.permissions?.write || state === "closed" || state === "merged"}>
            Merge
          </Button>
          <Button
            size={"sm"}
            variant={"danger"}
            onClick={handleClose}
            isLoading={isLoadingClose}
            disabled={!auth?.permissions?.write || state === "merged"}>
            {state === "closed" ? "Re-open" : "Close"}
          </Button>
        </div>
      </div>

      {loading && <LoadingScreen />}

      {nodes?.length && nodes.map((node, index) => <DiffNode key={index} node={node} />)}
    </>
  );
};
