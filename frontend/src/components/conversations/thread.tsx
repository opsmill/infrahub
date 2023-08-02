import { gql, useReactiveVar } from "@apollo/client";
import { formatISO, isBefore, parseISO } from "date-fns";
import * as R from "ramda";
import { useContext, useState } from "react";
import { toast } from "react-toastify";
import {
  PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "../../config/constants";
import { AuthContext } from "../../decorators/withAuth";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { createObject } from "../../graphql/mutations/objects/createObject";
import { updateObjectWithId } from "../../graphql/mutations/objects/updateObjectWithId";
import { branchVar } from "../../graphql/variables/branchVar";
import { dateVar } from "../../graphql/variables/dateVar";
import { classNames } from "../../utils/common";
import { stringifyWithoutQuotes } from "../../utils/string";
import { ALERT_TYPES, Alert } from "../alert";
import { Button } from "../button";
import { Checkbox } from "../checkbox";
import ModalConfirm from "../modal-confirm";
import { Tooltip } from "../tooltip";
import { AddComment } from "./add-comment";
import { Comment } from "./comment";

type tThread = {
  thread: any;
  refetch: Function;
};

// Sort by date desc
export const sortByDate = R.sort((a: any, b: any) =>
  isBefore(parseISO(a.created_at?.value || new Date()), parseISO(b.created_at?.value || new Date()))
    ? -1
    : 1
);

export const Thread = (props: tThread) => {
  const { thread, refetch } = props;

  const auth = useContext(AuthContext);

  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const [isLoading, setIsLoading] = useState(false);
  const [displayAddComment, setDisplayAddComment] = useState(false);
  const [confirmModal, setConfirmModal] = useState(false);
  const [markAsResolved, setMarkAsResolved] = useState(false);

  const handleSubmit = async (data: any) => {
    try {
      if (!data) {
        return;
      }

      const newObject = {
        text: {
          value: data.comment,
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

      refetch();

      setIsLoading(false);
    } catch (error: any) {
      console.error("An error occured while creating the comment: ", error);

      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={"An error occured while creating the comment"}
          details={error.message}
        />
      );

      setIsLoading(false);
    }
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
      kind: PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
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

    refetch();

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

  const MarkAsResolved = (
    <div className="flex items-center">
      <Button onClick={() => setConfirmModal(true)} disabled={isResolved}>
        <div className="mr-2">Resolved: </div>

        <Checkbox
          disabled={isResolved}
          enabled={isResolved || markAsResolved}
          onChange={() => setConfirmModal(true)}
        />
      </Button>
    </div>
  );

  const MarkAsResolvedWithTooltip = (
    <Tooltip message={"The resolution will be done after submitting the comment"}>
      {MarkAsResolved}
    </Tooltip>
  );

  return (
    <section
      className={classNames(
        isResolved ? "bg-gray-200" : "bg-custom-white",
        "p-4 m-4 rounded-lg relative"
      )}>
      <div className="">
        {sortedComments.map((comment: any, index: number) => (
          <Comment key={index} comment={comment} className={"border border-gray-200"} />
        ))}
      </div>

      <div className="flex">
        {displayAddComment && (
          <div className="flex-1">
            <AddComment
              onSubmit={handleSubmit}
              isLoading={isLoading}
              onClose={() => setDisplayAddComment(false)}
              disabled={!auth?.permissions?.write}
              additionalButtons={MarkAsResolvedWithTooltip}
            />
          </div>
        )}

        {!displayAddComment && (
          <div className="flex flex-1 justify-between">
            {MarkAsResolved}

            <Button onClick={() => setDisplayAddComment(true)} disabled={!auth?.permissions?.write}>
              Reply
            </Button>
          </div>
        )}
      </div>

      <ModalConfirm
        title="Confirm"
        description={"Are you sure you want to mark this thread as resolved?"}
        onCancel={() => setConfirmModal(false)}
        onConfirm={handleResolve}
        open={!!confirmModal}
        setOpen={() => setConfirmModal(false)}
        isLoading={isLoading}
      />
    </section>
  );
};
