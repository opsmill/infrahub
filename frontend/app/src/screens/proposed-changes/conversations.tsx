import { Button, BUTTON_TYPES } from "@/components/buttons/button";
import { AddComment } from "@/components/conversations/add-comment";
import { Thread } from "@/components/conversations/thread";
import { Avatar, AVATAR_SIZE } from "@/components/display/avatar";
import { Badge } from "@/components/display/badge";
import { DateDisplay } from "@/components/display/date-display";
import SlideOver from "@/components/display/slide-over";
import { List } from "@/components/table/list";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { Tooltip } from "@/components/ui/tooltip";
import {
  ACCOUNT_OBJECT,
  DEFAULT_BRANCH_NAME,
  PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
  PROPOSED_CHANGES_EDITABLE_STATE,
  PROPOSED_CHANGES_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
  PROPOSED_CHANGES_THREAD_OBJECT,
} from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { deleteObject } from "@/graphql/mutations/objects/deleteObject";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { getProposedChangesThreads } from "@/graphql/queries/proposed-changes/getProposedChangesThreads";
import { useAuth } from "@/hooks/useAuth";
import useQuery from "@/hooks/useQuery";
import ErrorScreen from "@/screens/errors/error-screen";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { branchesState, currentBranchAtom } from "@/state/atoms/branches.atom";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { constructPath } from "@/utils/fetch";
import { getProposedChangesStateBadgeType } from "@/utils/proposed-changes";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql, NetworkStatus } from "@apollo/client";
import { PencilIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { formatISO } from "date-fns";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { forwardRef, useImperativeHandle, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import DynamicForm from "@/components/form/dynamic-form";
import { schemaState } from "@/state/atoms/schema.atom";
import { AttributeType } from "@/utils/getObjectItemDisplayValue";
import { getUpdateMutationFromFormData } from "@/components/form/utils/mutations/getUpdateMutationFromFormData";
import { DynamicFieldProps, FormFieldValue } from "@/components/form/type";

type tConversations = {
  refetch?: Function;
};

export const Conversations = forwardRef((props: tConversations, ref) => {
  const { refetch: detailsRefetch } = props;
  const { proposedchange } = useParams();
  const [proposedChangesDetails] = useAtom(proposedChangedState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const auth = useAuth();
  const [isLoadingApprove, setIsLoadingApprove] = useState(false);
  const [isLoadingMerge, setIsLoadingMerge] = useState(false);
  const [isLoadingClose, setIsLoadingClose] = useState(false);
  const [showEditDrawer, setShowEditDrawer] = useState(false);
  const navigate = useNavigate();

  const queryString = getProposedChangesThreads({
    id: proposedchange,
    kind: PROPOSED_CHANGES_THREAD_OBJECT,
    accountKind: ACCOUNT_OBJECT,
  });

  const query = gql`
    ${queryString}
  `;

  const { error, data, refetch, networkStatus } = useQuery(query, {
    notifyOnNetworkStatusChange: true,
  });

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch }));

  const isGetProposedChangesThreadsLoadingForthFistTime = networkStatus === NetworkStatus.loading;

  if (isGetProposedChangesThreadsLoadingForthFistTime) {
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the conversations." />;
  }

  const threads = data
    ? data[PROPOSED_CHANGES_THREAD_OBJECT]?.edges?.map((edge: any) => edge.node)
    : [];
  const reviewers = proposedChangesDetails?.reviewers?.edges.map((edge: any) => edge.node) ?? [];
  const approvers = proposedChangesDetails?.approved_by?.edges.map((edge: any) => edge.node) ?? [];
  const approverId = auth?.data?.sub;
  const canApprove = !approvers?.map((a: any) => a.id).includes(approverId);
  const path = constructPath("/proposed-changes");
  const state = proposedChangesDetails?.state?.value;

  const handleSubmit = async ({ comment }: { comment: string }) => {
    let threadId;

    try {
      if (!approverId) return;

      const newDate = formatISO(new Date());

      const newThread = {
        change: {
          id: proposedchange,
        },
        label: {
          value: "Conversation",
        },
        created_at: {
          value: newDate,
        },
        resolved: {
          value: false,
        },
      };

      const threadMutationString = createObject({
        kind: PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
        data: stringifyWithoutQuotes(newThread),
      });

      const threadMutation = gql`
        ${threadMutationString}
      `;

      const result = await graphqlClient.mutate({
        mutation: threadMutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      threadId = result?.data[`${PROPOSED_CHANGES_CHANGE_THREAD_OBJECT}Create`]?.object?.id;

      const newComment = {
        text: {
          value: comment,
        },
        created_by: {
          id: approverId,
        },
        created_at: {
          value: newDate,
        },
        thread: {
          id: threadId,
        },
      };

      const mutationString = createObject({
        kind: PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
        data: stringifyWithoutQuotes(newComment),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Comment added"} />);

      await refetch();
    } catch (error: any) {
      if (threadId) {
        const mutationString = deleteObject({
          name: PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
          data: stringifyWithoutQuotes({
            id: threadId,
          }),
        });

        const mutation = gql`
          ${mutationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: { branch: branch?.name, date },
        });
      }

      console.error("An error occurred while creating the comment: ", error);
    }
  };

  const handleApprove = async () => {
    if (!approverId) {
      return;
    }

    setIsLoadingApprove(true);

    const oldApproversId = approvers.map((a: any) => a.id);
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

      if (detailsRefetch) {
        await detailsRefetch();
      }

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

      if (detailsRefetch) {
        detailsRefetch();
      }

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

      if (detailsRefetch) {
        detailsRefetch();
      }

      setIsLoadingClose(false);

      return;
    } catch (e) {
      console.error("Something went wrong while updating the object:", e);

      setIsLoadingClose(false);

      return;
    }
  };

  const columns = [
    {
      label: "ID",
      name: "id",
    },
    {
      label: "Name",
      name: "name",
    },
    {
      label: "Description",
      name: "description",
    },
    {
      label: "State",
      name: "state",
    },
    {
      label: "Source branch",
      name: "source_branch",
    },
    {
      label: "Destination branch",
      name: "desctination_branch",
    },
    {
      label: "Created by",
      name: "created_by",
    },
    {
      label: "Approvers",
      name: "approvers",
    },
    {
      label: "Reviewers",
      name: "reviewers",
    },
    {
      label: "Updated",
      name: "updated_at",
    },
    {
      label: "Actions",
      name: "actions",
    },
  ];

  const row = {
    values: {
      id: proposedchange,
      name: proposedChangesDetails?.name?.value,
      description: proposedChangesDetails?.description?.value,
      state: <Badge type={getProposedChangesStateBadgeType(state)}>{state}</Badge>,
      source_branch: <Badge>{proposedChangesDetails?.source_branch?.value}</Badge>,
      destination_branch: <Badge>{proposedChangesDetails?.destination_branch?.value}</Badge>,
      created_by: (
        <Tooltip enabled content={proposedChangesDetails?.created_by?.node?.display_label}>
          <Avatar
            size={AVATAR_SIZE.SMALL}
            name={proposedChangesDetails?.created_by?.node?.display_label}
            className="mr-2 bg-custom-blue-green"
          />
        </Tooltip>
      ),
      reviewers: (
        <>
          {reviewers.map((reviewer: any, index: number) => (
            <Tooltip key={index} message={reviewer.display_label}>
              <Avatar size={AVATAR_SIZE.SMALL} name={reviewer.display_label} className="mr-2" />
            </Tooltip>
          ))}
        </>
      ),
      approvers: (
        <>
          {approvers.map((approver: any, index: number) => (
            <Tooltip key={index} message={approver.display_label}>
              <Avatar size={AVATAR_SIZE.SMALL} name={approver.display_label} className="mr-2" />
            </Tooltip>
          ))}
        </>
      ),
      updated_at: <DateDisplay date={proposedChangesDetails?._updated_at} />,
      actions: (
        <>
          <Button
            onClick={handleApprove}
            isLoading={isLoadingApprove}
            disabled={!auth?.permissions?.write || !approverId || !canApprove}
            className="mr-2">
            Approve
          </Button>

          <Button
            onClick={handleMerge}
            buttonType={BUTTON_TYPES.VALIDATE}
            isLoading={isLoadingMerge}
            disabled={!auth?.permissions?.write || state === "closed" || state === "merged"}
            className="mr-2">
            Merge
          </Button>

          <Button
            onClick={handleClose}
            buttonType={BUTTON_TYPES.CANCEL}
            isLoading={isLoadingClose}
            disabled={!auth?.permissions?.write || state === "merged"}>
            {state === "closed" ? "Re-open" : "Close"}
          </Button>
        </>
      ),
    },
  };

  return (
    <div className="flex flex-col-reverse lg:flex-row">
      <div className="flex-1 p-4 min-w-[500px]">
        <div>
          {threads.map((item: any, index: number) => (
            <Thread key={index} thread={item} refetch={refetch} displayContext />
          ))}
        </div>

        <div className="bg-custom-white p-4 m-4 rounded-lg relative">
          <AddComment onSubmit={handleSubmit} />
        </div>
      </div>

      <div className="lg:max-w-[500px]">
        <div className="bg-custom-white flex flex-col justify-start rounded-bl-lg">
          <div className="py-4 px-4">
            <div className="flex items-center">
              <div className="flex flex-1">
                <div
                  onClick={() => navigate(path)}
                  className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline">
                  Proposed change
                </div>
              </div>

              <div>
                <Button
                  disabled={
                    !auth?.permissions?.write ||
                    !PROPOSED_CHANGES_EDITABLE_STATE.includes(proposedChangesDetails?.state?.value)
                  }
                  onClick={() => setShowEditDrawer(true)}
                  className="mr-4">
                  Edit
                  <PencilIcon className="ml-2 h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-200">
            <List columns={columns} row={row} />
          </div>
        </div>
      </div>

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <span className="text-lg font-semibold mr-3">
                {proposedChangesDetails?.display_label}
              </span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>
            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {PROPOSED_CHANGES_THREAD_OBJECT}
            </span>
            <div className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-custom-blue-500 ring-1 ring-inset ring-custom-blue-500/10">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-custom-blue-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              ID: {proposedChangesDetails?.id}
            </div>
          </div>
        }
        open={showEditDrawer}
        setOpen={setShowEditDrawer}>
        <ProposedChangeEditForm
          initialData={proposedChangesDetails}
          onSuccess={() => {
            setShowEditDrawer(false);
            if (detailsRefetch) detailsRefetch();
            refetch();
          }}
        />
      </SlideOver>
    </div>
  );
});

type ProposedChangeEditFormProps = {
  initialData: Record<string, AttributeType>;
  onSuccess?: () => void;
};

const ProposedChangeEditForm = ({ initialData, onSuccess }: ProposedChangeEditFormProps) => {
  const nodes = useAtomValue(schemaState);
  const branches = useAtomValue(branchesState);
  const currentBranch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const proposedChangeSchema = nodes.find(({ kind }) => kind === PROPOSED_CHANGES_OBJECT);

  if (!proposedChangeSchema) return null;

  const fields: Array<DynamicFieldProps> = [
    {
      name: "name",
      type: "Text",
      label: "Name",
      defaultValue: { source: { type: "user" }, value: initialData?.name?.value },
      rules: {
        validate: {
          required: ({ value }: FormFieldValue) => {
            return (value !== null && value !== undefined && value !== "") || "Required";
          },
        },
      },
    },
    {
      name: "description",
      type: "TextArea",
      label: "Description",
      defaultValue: { source: { type: "user" }, value: initialData?.description?.value },
    },
    {
      name: "source_branch",
      type: "enum",
      label: "Source Branch",
      defaultValue: { source: { type: "user" }, value: initialData?.source_branch?.value },
      items: branches.map(({ id, name }) => ({ id, name })),
      rules: {
        validate: {
          required: ({ value }: FormFieldValue) => {
            return (value !== null && value !== undefined) || "Required";
          },
        },
      },
      disabled: true,
    },
    {
      name: "destination_branch",
      type: "enum",
      label: "Destination Branch",
      defaultValue: { source: { type: "user" }, value: initialData?.destination_branch?.value },
      items: branches.map(({ id, name }) => ({ id, name })),
      disabled: true,
    },
    {
      name: "reviewers",
      label: "Reviewers",
      type: "relationship",
      relationship: { cardinality: "many", peer: ACCOUNT_OBJECT } as any,
      schema: {} as any,
      defaultValue: {
        source: { type: "user" },
        value:
          initialData?.reviewers?.edges
            .map((edge: any) => ({ id: edge?.node?.id }))
            .filter(Boolean) ?? [],
      },
      options: initialData?.reviewers?.edges.map(({ node }) => ({
        id: node?.id,
        name: node?.display_label,
      })),
    },
  ];

  async function onSubmit(formData: any) {
    const updatedObject = getUpdateMutationFromFormData({ formData, fields });

    console.log(updatedObject);
    if (Object.keys(updatedObject).length) {
      try {
        const mutationString = updateObjectWithId({
          kind: proposedChangeSchema?.kind,
          data: stringifyWithoutQuotes({
            id: initialData.id,
            ...updatedObject,
          }),
        });

        const mutation = gql`
          ${mutationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: { branch: currentBranch?.name, date },
        });

        toast(
          () => (
            <Alert type={ALERT_TYPES.SUCCESS} message={`${proposedChangeSchema?.name} updated`} />
          ),
          {
            toastId: "alert-success-updated",
          }
        );

        if (onSuccess) onSuccess();
      } catch (e) {
        console.error("Something went wrong while updating the object:", e);
      }
    }
  }

  return <DynamicForm onSubmit={onSubmit} fields={fields} className="p-4" />;
};
