import {
  PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "@/config/constants";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import { useDeleteObjectMutation } from "@/entities/nodes/object/domain/delete-object.mutation";
import { AddComment } from "@/shared/components/conversations/add-comment";
import { Card } from "@/shared/components/ui/card";
import { FormRef } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";
import { formatISO } from "date-fns";
import { HTMLAttributes, useRef } from "react";
import { ProposedChangeEvents } from "./proposed-change-events";

export const Overview = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => {
  const formRef = useRef<FormRef>(null);
  const createObject = useCreateObjectMutation();
  const deleteObject = useDeleteObjectMutation();

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
      <ProposedChangeEvents />

      <Card>
        <AddComment ref={formRef} onSubmit={handleSubmit} />
      </Card>
    </div>
  );
};
