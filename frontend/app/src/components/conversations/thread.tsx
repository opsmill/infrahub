import { Button } from "@/components/buttons/button";
import { Checkbox } from "@/components/inputs/checkbox";
import ModalConfirm from "@/components/modals/modal-confirm";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Tooltip } from "@/components/ui/tooltip";
import {
  DIFF_TABS,
  PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT,
  PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
  PROPOSED_CHANGES_OBJECT_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { useAuth } from "@/hooks/useAuth";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { classNames } from "@/utils/common";
import { getThreadTitle } from "@/utils/diff";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { formatISO, isBefore, parseISO } from "date-fns";
import { useAtomValue } from "jotai/index";
import * as R from "ramda";
import { useState } from "react";
import { toast } from "react-toastify";
import { AddComment } from "./add-comment";
import { Comment } from "./comment";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "@/config/qsp";

type tThread = {
  thread: any;
  refetch?: Function;
  displayContext?: boolean; // For conversation view only
};

// Sort by date desc
export const sortByDate = R.sort((a: any, b: any) =>
  isBefore(parseISO(a.created_at?.value || new Date()), parseISO(b.created_at?.value || new Date()))
    ? -1
    : 1
);

export const Thread = (props: tThread) => {
  const { thread, refetch, displayContext } = props;

  const auth = useAuth();

  const [qspTab] = useQueryParam(QSP.PROPOSED_CHANGES_TAB, StringParam);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);
  const [displayAddComment, setDisplayAddComment] = useState(false);
  const [confirmModal, setConfirmModal] = useState(false);
  const [markAsResolved, setMarkAsResolved] = useState(false);

  const handleSubmit = async ({ comment }: { comment: string }) => {
    try {
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

      const mutationString = createObject({
        kind: PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
        data: stringifyWithoutQuotes(newObject),
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

      if (markAsResolved) {
        // If the resolved checkbox was checked, we need to resolve the thread after the comment
        await handleResolve();
      }

      if (refetch) {
        await refetch();
      }

      setIsLoading(false);
      setDisplayAddComment(false);
    } catch (error: any) {
      console.error("An error occurred while creating the comment: ", error);

      setIsLoading(false);
    }
  };

  const getMutation = () => {
    // for artifacts view
    if (qspTab === DIFF_TABS.ARTIFACTS) {
      return PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT;
    }

    // for conversations view
    if (displayContext) {
      return PROPOSED_CHANGES_CHANGE_THREAD_OBJECT;
    }

    // for object views
    return PROPOSED_CHANGES_OBJECT_THREAD_OBJECT;
  };

  const handleResolve = async () => {
    if (!thread.id) {
      return;
    }

    if (displayAddComment && !markAsResolved) {
      // If we want to resolve while submitting, we need to stop here and let the user submit the comment form
      setMarkAsResolved(true);
      setConfirmModal(false);
      return;
    }

    const mutationString = updateObjectWithId({
      kind: getMutation(),
      data: stringifyWithoutQuotes({
        id: thread.id,
        resolved: {
          value: true,
        },
      }),
    });

    const mutation = gql`
      ${mutationString}
    `;

    await graphqlClient.mutate({
      mutation,
      context: { branch: branch?.name, date },
    });

    if (refetch) {
      refetch();
    }

    if (confirmModal) {
      setConfirmModal(false);
    }

    if (displayAddComment) {
      setDisplayAddComment(false);
    }

    toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Thread resolved"} />);
  };

  const comments = thread?.comments?.edges?.map((comment: any) => comment.node) ?? [];
  const sortedComments = sortByDate(comments);
  const isResolved = thread?.resolved?.value;
  const idForLabel = `checkbox-resolve-thread${thread.id}`;

  const MarkAsResolved = (
    <div className="flex items-center gap-2">
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
    <section
      className={classNames(
        isResolved ? "bg-gray-200" : "bg-custom-white",
        "p-4 rounded-lg relative"
      )}
      data-testid="thread"
      data-cy="thread">
      {displayContext && getThreadTitle(thread)}

      <div>
        {sortedComments.map((comment: any, index: number) => (
          <Comment
            key={index}
            author={comment?.created_by?.node?.display_label ?? "Anonymous"}
            createdAt={comment?.created_at?.value}
            content={comment?.text?.value ?? ""}
            className={"border border-gray-200"}
          />
        ))}
      </div>

      {displayAddComment ? (
        <div className="flex-1">
          <AddComment
            onSubmit={handleSubmit}
            onCancel={() => setDisplayAddComment(false)}
            additionalButtons={MarkAsResolvedWithTooltip}
          />
        </div>
      ) : (
        <div className="flex flex-1 justify-between">
          {MarkAsResolved}

          <Button onClick={() => setDisplayAddComment(true)} disabled={!auth?.permissions?.write}>
            Reply
          </Button>
        </div>
      )}

      <ModalConfirm
        title="Confirm"
        description={"Are you sure you want to mark this thread as resolved?"}
        onCancel={() => setConfirmModal(false)}
        onConfirm={handleResolve}
        open={confirmModal}
        setOpen={() => setConfirmModal(false)}
        isLoading={isLoading}
      />
    </section>
  );
};
