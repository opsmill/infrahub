import { formatISO } from "date-fns";
import { type HTMLAttributes, useRef } from "react";
import { useParams } from "react-router";

import { queryClient } from "@/shared/api/rest/client";
import { Card } from "@/shared/components/ui/card";
import type { FormRef } from "@/shared/components/ui/form";
import {
  PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
  PROPOSED_CHANGES_THREAD_OBJECT,
} from "@/shared/config/constants";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import { useDeleteObjectMutation } from "@/entities/nodes/object/domain/delete-object.mutation";
import { AddComment } from "@/entities/proposed-changes/ui/conversations/add-comment";

import { ProposedChangeEvents } from "./proposed-change-events";

export const Overview = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => {
  const formRef = useRef<FormRef>(null);
  const createObject = useCreateObjectMutation();
  const deleteObject = useDeleteObjectMutation();
  const { proposedChangeId } = useParams();
  const auth = useAuth();
  const approverId = auth.user?.id;

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

                queryClient.invalidateQueries({
                  predicate: (query) =>
                    query.queryKey.includes(PROPOSED_CHANGES_THREAD_OBJECT) ||
                    query.queryKey.includes("events"),
                });
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
    <div className={classNames("min-w-[350px] grow space-y-4", className)} {...props}>
      <ProposedChangeEvents />

      <Card>
        <AddComment ref={formRef} onSubmit={handleSubmit} />
      </Card>
    </div>
  );
};
