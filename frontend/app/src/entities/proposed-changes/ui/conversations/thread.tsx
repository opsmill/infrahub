import { gql, useQuery } from "@apollo/client";
import { formatISO } from "date-fns";
import { useState } from "react";
import { toast } from "react-toastify";
import * as R from "remeda";

import { queryClient } from "@/shared/api/rest/client";
import { Checkbox } from "@/shared/components/inputs/checkbox";
import { ModalConfirm } from "@/shared/components/modals/modal-confirm";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { PROPOSED_CHANGES_THREAD_COMMENT_OBJECT } from "@/shared/config/constants";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { getThreadTitle } from "@/entities/diff/ui/diff-utils";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getObjectPermissionsQuery } from "@/entities/permission/queries/getObjectPermissions";
import { getPermission } from "@/entities/permission/utils";

import { AddComment } from "./add-comment";
import { Comment } from "./comment";

type tThread = {
  thread: any;
  refetch?: Function;
  displayContext?: boolean; // For conversation view only
};

export const Thread = (props: tThread) => {
  const { thread, refetch, displayContext } = props;

  const auth = useAuth();

  const [isLoading, setIsLoading] = useState(false);
  const [displayAddComment, setDisplayAddComment] = useState(false);
  const [confirmModal, setConfirmModal] = useState(false);
  const [markAsResolved, setMarkAsResolved] = useState(false);
  const createObject = useCreateObjectMutation();
  const updateObject = useUpdateObjectMutation();

  const { loading, data } = useQuery(
    gql(getObjectPermissionsQuery(PROPOSED_CHANGES_THREAD_COMMENT_OBJECT))
  );

  const permission =
    data && getPermission(data?.[PROPOSED_CHANGES_THREAD_COMMENT_OBJECT]?.permissions?.edges);

  const handleSubmit = async ({ comment }: { comment: string }) => {
    setIsLoading(true);

    const newObject = {
      text: {
        value: comment,
      },
      thread: {
        id: thread.id,
      },
      created_by: {
        id: auth?.data?.sub,
      },
      created_at: {
        value: formatISO(new Date()),
      },
    };

    await createObject.mutateAsync(
      {
        objectKind: PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
        data: newObject,
      },
      {
        onSuccess: async () => {
          if (markAsResolved) {
            // If the resolved checkbox was checked, we need to resolve the thread after the comment
            await handleResolve();
          }

          if (refetch) {
            await refetch();
          }

          queryClient.invalidateQueries({
            predicate: (query) => query.queryKey.includes(thread.id),
          });

          setIsLoading(false);
          setDisplayAddComment(false);
        },
        onError: (error) => {
          console.error("An error occurred while creating the comment: ", error);

          setIsLoading(false);
        },
      }
    );
  };

  const handleResolve = async () => {
    if (!thread.id) {
      return;
    }

    if (displayAddComment && !markAsResolved) {
      setMarkAsResolved(true);
      setConfirmModal(false);
      return;
    }

    setIsLoading(true);

    await updateObject.mutateAsync(
      {
        objectKind: thread.__typename,
        data: {
          id: thread.id,
          resolved: {
            value: true,
          },
        },
      },
      {
        onSuccess: () => {
          if (refetch) {
            refetch();
          }

          if (confirmModal) {
            setConfirmModal(false);
          }

          if (displayAddComment) {
            setDisplayAddComment(false);
          }

          queryClient.invalidateQueries({
            predicate: (query) => query.queryKey.includes(thread.id),
          });

          toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Thread resolved"} />);
          setIsLoading(false);
        },
        onError: (error) => {
          console.error("An error occurred while resolving the thread: ", error);
          setIsLoading(false);
        },
      }
    );
  };

  const comments = thread?.comments?.edges?.map((comment: any) => comment.node) ?? [];

  const sortedComments = R.sortBy(comments, (x) => new Date(x.created_at.value).getTime());

  const isResolved = thread?.resolved?.value;
  const idForLabel = `checkbox-resolve-thread${thread?.id}`;

  const MarkAsResolved = (
    <div className="flex items-center gap-2 text-sm">
      <Checkbox
        id={idForLabel}
        disabled={isResolved}
        checked={isResolved || markAsResolved}
        onChange={() => setConfirmModal(true)}
      />
      <label htmlFor={idForLabel} className={isResolved ? "cursor-default" : "cursor-pointer"}>
        {isResolved ? "Resolved" : "Resolve thread"}
      </label>
    </div>
  );

  const MarkAsResolvedWithTooltip = (
    <Tooltip enabled content={"The resolution will be done after submitting the comment"}>
      {MarkAsResolved}
    </Tooltip>
  );

  return (
    <Card
      className={classNames(
        "relative flex flex-col gap-2 rounded-md p-2",
        isResolved && "bg-gray-200"
      )}
      data-testid="thread"
      data-cy="thread"
    >
      {displayContext && getThreadTitle(thread)}

      {sortedComments.map((comment: any, index: number) => (
        <Comment
          key={index}
          author={comment?.created_by?.node ? getNodeLabel(comment.created_by.node) : "Anonymous"}
          createdAt={comment?.created_at?.value}
          content={comment?.text?.value ?? ""}
          className={"border border-gray-200"}
        />
      ))}

      {displayAddComment ? (
        <AddComment
          onSubmit={handleSubmit}
          onCancel={() => setDisplayAddComment(false)}
          additionalButtons={MarkAsResolvedWithTooltip}
        />
      ) : (
        <div className="flex justify-between">
          {MarkAsResolved}

          <Button
            variant={"outline"}
            onClick={() => setDisplayAddComment(true)}
            disabled={loading || !permission?.create?.isAllowed}
          >
            Reply
          </Button>
        </div>
      )}

      <ModalConfirm
        title="Confirm"
        description="Are you sure you want to mark this thread as resolved?"
        onConfirm={handleResolve}
        isOpen={confirmModal}
        onOpenChange={setConfirmModal}
        isLoading={isLoading}
      />
    </Card>
  );
};
