import {
  ACCOUNT_GENERIC_OBJECT,
  PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
  PROPOSED_CHANGES_THREAD_OBJECT,
} from "@/config/constants";
import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import { useDeleteObject } from "@/entities/nodes/object/domain/delete-object.mutation";
import { getProposedChangesThreads } from "@/entities/proposed-changes/api/getProposedChangesThreads";
import useQuery from "@/shared/api/graphql/useQuery";
import { AddComment } from "@/shared/components/conversations/add-comment";
import { Thread } from "@/shared/components/conversations/thread";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Card } from "@/shared/components/ui/card";
import { FormRef } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";
import { NetworkStatus, gql } from "@apollo/client";
import { formatISO } from "date-fns";
import { HTMLAttributes, useRef } from "react";
import { useParams } from "react-router";

export const Conversations = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => {
  const { proposedChangeId } = useParams();
  const auth = useAuth();
  const formRef = useRef<FormRef>(null);
  const createObject = useCreateObjectMutation();
  const deleteObject = useDeleteObject();

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
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the conversations." />;
  }

  const threads = data
    ? data[PROPOSED_CHANGES_THREAD_OBJECT]?.edges?.map((edge: any) => edge.node)
    : [];
  const approverId = auth?.data?.sub;

  const handleSubmit = async ({ comment }: { comment: string }) => {
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

    await createObject.mutateAsync(
      {
        objectKind: PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
        data: newThread,
      },
      {
        onSuccess: async (newThread) => {
          const threadId = newThread.id;

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

          await createObject.mutateAsync(
            {
              objectKind: PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
              data: newComment,
            },
            {
              onSuccess: async () => {
                formRef.current?.reset();
                await refetch();
                formRef.current?.reset();
              },
              onError: async (error) => {
                if (threadId) {
                  await deleteObject.mutateAsync({
                    objectKind: PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
                    objectId: threadId,
                  });
                }

                console.error("An error occurred while creating the comment: ", error);
              },
            }
          );
        },
      }
    );
  };

  return (
    <div className={classNames("grow space-y-4 min-w-[350px]", className)} {...props}>
      {threads.map((item: any, index: number) => (
        <Thread key={index} thread={item} refetch={refetch} displayContext />
      ))}

      <Card>
        <AddComment ref={formRef} onSubmit={handleSubmit} />
      </Card>
    </div>
  );
};
