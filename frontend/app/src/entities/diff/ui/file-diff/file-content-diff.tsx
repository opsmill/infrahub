import { gql, useQuery } from "@apollo/client";
import { formatISO } from "date-fns";
import { useAtom } from "jotai";
import { PencilLineIcon } from "lucide-react";
import { useState } from "react";
import { Diff, getChangeKey, Hunk, parseDiff } from "react-diff-view";

import Accordion from "@/shared/components/display/accordion";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import {
  PROPOSED_CHANGES_FILE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "@/shared/config/constants";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useGetFile } from "@/entities/diff/ui/queries/get-file.query";
import type { FileDiffFile } from "@/entities/diff/domain/get-files-diff";
import { getProposedChangesFilesThreads } from "@/entities/proposed-changes/api/getProposedChangesFilesThreads";
import { AddComment } from "@/entities/proposed-changes/ui/conversations/add-comment";
import { Thread } from "@/entities/proposed-changes/ui/conversations/thread";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import "react-diff-view/style/index.css";

import { Button } from "react-aria-components";
import { useParams } from "react-router";
import { toast } from "react-toastify";
import sha from "sha1";
import { diffLines, formatLines } from "unidiff";

import { Row } from "@/shared/components/container";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { DiffBadge } from "@/entities/diff/ui/node-diff/utils";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import { useDeleteObjectMutation } from "@/entities/nodes/object/domain/delete-object.mutation";

interface FileContentDiffProps {
  repositoryId: string;
  repositoryDisplayName?: string | null;
  file: FileDiffFile;
  commitFrom: string;
  commitTo: string;
}

const fakeIndex = () => {
  return sha(Math.random() * 100_000).slice(0, 9);
};

const appendGitDiffHeaderIfNeeded = (diffText: string) => {
  if (diffText.startsWith("diff --git")) {
    return diffText;
  }

  const segments = ["diff --git a/a b/b", `index ${fakeIndex()}..${fakeIndex()} 100644`, diffText];

  return segments.join("\n");
};

const shouldDisplayAddComment = (state: any, change: any) => {
  const { side, newLineNumber, oldLineNumber, lineNumber, isInsert, isDelete } = state;

  if (side === "new") {
    return (
      (newLineNumber && newLineNumber === change.newLineNumber) ||
      (lineNumber && lineNumber === change.lineNumber && isInsert === change.isInsert)
    );
  }

  return (
    (oldLineNumber && oldLineNumber === change.oldLineNumber) ||
    (lineNumber && lineNumber === change.lineNumber && isDelete === change.isDelete)
  );
};

const findThreadByChange = (
  threads: any[],
  change: any,
  commitFrom?: string,
  commitTo?: string
) => {
  const isChangeOnLeftSide = change?.isDelete;
  const isChangeOnRightSide = change?.isInsert;
  const isChangeOnBothSide = change?.isNormal;

  return threads.find((thread) => {
    const threadLineNumber = thread?.line_number?.value;
    const threadCommit = thread?.commit?.value;

    const isThreadOnLeftSide = threadCommit === commitFrom || !threadCommit === !commitFrom;
    if (isChangeOnLeftSide && isThreadOnLeftSide && threadLineNumber === change.lineNumber) {
      return true;
    }

    const isThreadOnRightSide = threadCommit === commitTo;
    if (isChangeOnRightSide && isThreadOnRightSide && threadLineNumber === change.lineNumber) {
      return true;
    }

    return !!(
      isChangeOnBothSide &&
      ((isThreadOnLeftSide && threadLineNumber === change.oldLineNumber) ||
        (isThreadOnRightSide && threadLineNumber === change.newLineNumber))
    );
  });
};

export function FileContentDiff({
  repositoryId,
  repositoryDisplayName,
  file,
  commitFrom,
  commitTo,
}: FileContentDiffProps) {
  const { proposedChangeId } = useParams();
  const auth = useAuth();
  const [schemaList] = useAtom(nodeSchemasAtom);
  const [displayAddComment, setDisplayAddComment] = useState<any>({});
  const createObject = useCreateObjectMutation();
  const deleteObject = useDeleteObjectMutation();

  const {
    data: previousFile,
    isPending: isPendingPreviousFile,
    error: previousFileError,
  } = useGetFile({
    repositoryId,
    filePath: file.location,
    commit: commitFrom,
  });

  const {
    data: newFile,
    isPending: isPendingNewFile,
    error: newFileError,
  } = useGetFile({
    repositoryId,
    filePath: file.location,
    commit: commitTo,
  });

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_FILE_THREAD_OBJECT);

  const queryString =
    schemaData && proposedChangeId
      ? getProposedChangesFilesThreads({
          id: proposedChangeId,
          kind: schemaData.kind,
        })
      : ""; // Empty query to make the gql parsing work

  const query = queryString
    ? gql`
        ${queryString}
      `
    : "";

  const { loading, error, data, refetch } = query
    ? useQuery(query, { skip: !schemaData })
    : { loading: false, error: null, data: null, refetch: null };

  const threads =
    data && schemaData?.kind ? data[schemaData?.kind]?.edges?.map((edge: any) => edge.node) : [];
  const approverId = auth?.data?.sub;

  const handleCloseComment = () => {
    setDisplayAddComment({});
  };

  const handleSubmitComment = async ({ comment }: { comment: string }) => {
    if (!comment || !approverId) {
      return;
    }

    const newDate = formatISO(new Date());

    const lineNumber = displayAddComment.isNormal
      ? displayAddComment.side === "new"
        ? displayAddComment.newLineNumber
        : displayAddComment.oldLineNumber
      : displayAddComment.lineNumber;

    const label = `${repositoryDisplayName} - ${file.location}:${lineNumber}`;

    const newThread = {
      change: {
        id: proposedChangeId,
      },
      label: {
        value: label,
      },
      created_at: {
        value: newDate,
      },
      created_by: {
        id: approverId,
      },
      resolved: {
        value: false,
      },
      commit: {
        value: displayAddComment.side === "new" ? commitTo : commitFrom,
      },
      line_number: {
        value: lineNumber,
      },
      file: {
        value: file.location,
      },
      repository: {
        id: repositoryId,
      },
    };

    await createObject.mutateAsync(
      {
        objectKind: PROPOSED_CHANGES_FILE_THREAD_OBJECT,
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
                if (refetch) refetch();
                handleCloseComment();
              },
              onError: async (error) => {
                await deleteObject.mutateAsync({
                  objectKind: PROPOSED_CHANGES_FILE_THREAD_OBJECT,
                  objectId: threadId,
                });

                console.error("An error occurred while creating the comment: ", error);

                toast(
                  <Alert
                    type={ALERT_TYPES.ERROR}
                    message={"An error occurred while creating the comment"}
                    details={error.message}
                  />
                );
              },
            }
          );
        },
      }
    );
  };

  const getWidgets = (hunks: any) => {
    const changes = hunks.reduce((result: any, { changes }: any) => [...result, ...changes], []);

    return changes.reduce((widgets: any, change: any) => {
      const changeKey = getChangeKey(change);

      if (shouldDisplayAddComment(displayAddComment, change)) {
        return {
          ...widgets,
          [changeKey]: <AddComment onSubmit={handleSubmitComment} onCancel={handleCloseComment} />,
        };
      }

      const thread = findThreadByChange(threads, change, commitFrom, commitTo);

      if (thread) {
        return {
          ...widgets,
          [changeKey]: <Thread thread={thread} refetch={refetch} />,
        };
      }

      if (!change.comments) {
        return widgets;
      }

      return {
        ...widgets,
        [changeKey]: change?.comments?.map((comment: any, index: number) => (
          <div key={index} className="m-2 rounded-md border border-custom-blue-500 bg-white p-4">
            {comment.message}
          </div>
        )),
      };
    }, {});
  };

  const renderGutter = (options: any) => {
    const { renderDefault, wrapInAnchor, inHoverState, side, change } = options;

    const handleClick = () => {
      setDisplayAddComment({ side, ...change });
    };

    const thread = findThreadByChange(threads, change, commitFrom, commitTo);

    if (thread || !auth?.isAuthenticated || !proposedChangeId) {
      // Do not display the add button if there is already a thread
      return wrapInAnchor(renderDefault());
    }

    return (
      <>
        {wrapInAnchor(renderDefault())}

        {inHoverState && (
          <Button
            className="absolute top-1/2 left-1/2 z-10 inline-flex w-full -translate-x-1/2 -translate-y-1/2 items-center justify-center bg-gray-200 p-1"
            onClick={handleClick}
          >
            <PencilLineIcon className="size-3.5" />
          </Button>
        )}
      </>
    );
  };

  if (loading || isPendingPreviousFile || isPendingNewFile) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error || previousFileError || newFileError) {
    return <ErrorScreen message="Something went wrong when fetching the file differences." />;
  }

  if (!previousFile && !newFile) {
    return null;
  }

  const diff = formatLines(diffLines(previousFile ?? "", newFile ?? ""), {
    context: 3,
    aname: commitFrom,
    bname: commitTo,
  });

  const [fileContent] = parseDiff(appendGitDiffHeaderIfNeeded(diff), {
    nearbySequences: "zip",
  });

  return (
    <div className={"m-4 rounded-lg bg-white p-2 shadow-sm"}>
      <Accordion
        title={
          <Row>
            <DiffBadge status={file.action.toUpperCase()} />
            {file.location}
          </Row>
        }
      >
        <div className="flex">
          <div className="flex-1">
            {commitFrom && <span className="font-normal italic">Commit: {commitFrom}</span>}
          </div>

          <div className="flex-1">
            {commitTo && <span className="font-normal italic">Commit: {commitTo}</span>}
          </div>
        </div>

        <div className="ml-2 bg-gray-50">
          <Diff
            key={`${sha(diff)}${previousFile ? sha(previousFile) : ""}${newFile ? sha(newFile) : ""}`}
            hunks={fileContent.hunks}
            viewType="split"
            diffType={fileContent.type}
            renderGutter={renderGutter}
            widgets={getWidgets(fileContent.hunks)}
            optimizeSelection
          >
            {(hunks) => hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)}
          </Diff>
        </div>
      </Accordion>
    </div>
  );
}
