import { gql, useQuery } from "@apollo/client";
import { PencilLineIcon } from "lucide-react";
import { formatISO } from "date-fns";
import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { Diff, getChangeKey, Hunk, parseDiff } from "react-diff-view";

import { fetchStream } from "@/shared/api/rest/fetch";
import { Button } from "@/shared/components/buttons/button";
import Accordion from "@/shared/components/display/accordion";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { CONFIG } from "@/shared/config/config";
import {
  PROPOSED_CHANGES_FILE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { getProposedChangesFilesThreads } from "@/entities/proposed-changes/api/getProposedChangesFilesThreads";
import { AddComment } from "@/entities/proposed-changes/ui/conversations/add-comment";
import { Thread } from "@/entities/proposed-changes/ui/conversations/thread";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import "react-diff-view/style/index.css";

import { useQueryState } from "nuqs";
import { useParams } from "react-router";
import { toast } from "react-toastify";
import sha from "sha1";
import { diffLines, formatLines } from "unidiff";

import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import { useDeleteObjectMutation } from "@/entities/nodes/object/domain/delete-object.mutation";

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

export const FileContentDiff = (props: any) => {
  const { repositoryId, repositoryDisplayName, file, commitFrom, commitTo } = props;

  const { proposedChangeId } = useParams();
  const [branchOnly] = useQueryState(QSP.BRANCH_FILTER_BRANCH_ONLY);
  const [timeFrom] = useQueryState(QSP.BRANCH_FILTER_TIME_FROM);
  const [timeTo] = useQueryState(QSP.BRANCH_FILTER_TIME_TO);
  const auth = useAuth();
  const [schemaList] = useAtom(nodeSchemasAtom);
  const [isLoading, setIsLoading] = useState(false);
  const [previousFile, setPreviousFile] = useState(false);
  const [newFile, setNewFile] = useState(false);
  const [displayAddComment, setDisplayAddComment] = useState<any>({});
  const createObject = useCreateObjectMutation();
  const deleteObject = useDeleteObjectMutation();

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

  const fetchFileDetails = useCallback(async (commit: string, setState: Function) => {
    setIsLoading(true);

    try {
      const url = CONFIG.FILES_CONTENT_URL(repositoryId, file.location);

      const options: string[][] = [
        ["branch_only", branchOnly ?? ""],
        ["time_from", timeFrom ?? ""],
        ["time_to", timeTo ?? ""],
        ["commit", commit ?? ""],
      ].filter(([, v]) => v !== undefined && v !== "");

      const qsp = new URLSearchParams(options);

      const urlWithQsp = `${url}?${options.length ? `&${qsp.toString()}` : ""}`;

      const fileResult = await fetchStream(urlWithQsp);

      setState(fileResult);
    } catch (err) {
      console.error("Error while loading files diff: ", err);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading files diff" />);
    }

    setIsLoading(false);
  }, []);

  const setFileDetailsInState = useCallback(async () => {
    await fetchFileDetails(commitFrom, setPreviousFile);
    await fetchFileDetails(commitTo, setNewFile);
  }, []);

  useEffect(() => {
    setFileDetailsInState();
  }, []);

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
                setIsLoading(false);
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

                setIsLoading(false);
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
            className="absolute top-1/2 left-1/2 z-10 -translate-x-1/2 -translate-y-1/2 transform"
            onClick={handleClick}
          >
            <PencilLineIcon className="h-3 w-3" />
          </Button>
        )}
      </>
    );
  };

  if (loading || isLoading) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the file differences." />;
  }

  if (!previousFile && !newFile) {
    return null;
  }

  const diff = formatLines(diffLines(previousFile, newFile), {
    context: 3,
    aname: commitFrom,
    bname: commitTo,
  });

  const [fileContent] = parseDiff(appendGitDiffHeaderIfNeeded(diff), {
    nearbySequences: "zip",
  });

  return (
    <div className={"m-4 rounded-lg bg-white p-2 shadow-sm"}>
      <Accordion title={file.location}>
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
            key={`${sha(diff)}${previousFile ? sha(previousFile) : ""}`}
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
};
