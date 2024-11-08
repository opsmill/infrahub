import { AddComment } from "@/components/conversations/add-comment";
import { Thread } from "@/components/conversations/thread";
import { Card } from "@/components/ui/card";
import { FormRef } from "@/components/ui/form";
import {
  ACCOUNT_GENERIC_OBJECT,
  PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
  PROPOSED_CHANGES_THREAD_OBJECT,
} from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { deleteObject } from "@/graphql/mutations/objects/deleteObject";
import { getProposedChangesThreads } from "@/graphql/queries/proposed-changes/getProposedChangesThreads";
import { useAuth } from "@/hooks/useAuth";
import useQuery from "@/hooks/useQuery";
import ErrorScreen from "@/screens/errors/error-screen";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { classNames } from "@/utils/common";
import { stringifyWithoutQuotes } from "@/utils/string";
import { NetworkStatus, gql } from "@apollo/client";
import { formatISO } from "date-fns";
import { useAtomValue } from "jotai/index";
import { HTMLAttributes, useRef } from "react";
import { useParams } from "react-router-dom";

export const Conversations = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => {
  const { proposedChangeId } = useParams();
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const auth = useAuth();
  const formRef = useRef<FormRef>(null);

  const queryString = getProposedChangesThreads({
    id: proposedChangeId,
    kind: PROPOSED_CHANGES_THREAD_OBJECT,
    accountKind: ACCOUNT_GENERIC_OBJECT,
  });

  const query = gql`
    ${queryString}
  `;

  const { error, data, refetch, networkStatus } = useQuery(query, {
    notifyOnNetworkStatusChange: true,
  });

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
  const approverId = auth?.data?.sub;

  const handleSubmit = async ({ comment }: { comment: string }) => {
    let threadId;

    try {
      if (!approverId) return;

      const newDate = formatISO(new Date());

      const newThread = {
        change: {
          id: proposedChangeId,
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

      formRef.current?.reset();
      await refetch();
      formRef.current?.reset();
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

  return (
    <div className={classNames("flex-grow space-y-4 min-w-[350px]", className)} {...props}>
      {threads.map((item: any, index: number) => (
        <Thread key={index} thread={item} refetch={refetch} displayContext />
      ))}

      <Card>
        <AddComment ref={formRef} onSubmit={handleSubmit} />
      </Card>
    </div>
  );
};
