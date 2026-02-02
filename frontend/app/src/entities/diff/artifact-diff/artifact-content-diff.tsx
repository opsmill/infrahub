import { gql, useQuery } from "@apollo/client";
import { formatISO } from "date-fns";
import { useAtom } from "jotai";
import { PencilLineIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Diff, getChangeKey, Hunk, parseDiff } from "react-diff-view";
import { useParams } from "react-router";
import { toast } from "react-toastify";
import sha from "sha1";
import { diffLines, formatLines } from "unidiff";

import { fetchStream } from "@/shared/api/rest/fetch";
import { Button } from "@/shared/components/buttons/button";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { CONFIG } from "@/shared/config/config";
import {
  PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT,
  PROPOSED_CHANGES_FILE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "@/shared/config/constants";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import { useDeleteObjectMutation } from "@/entities/nodes/object/domain/delete-object.mutation";
import { getProposedChangesArtifactsThreads } from "@/entities/proposed-changes/api/getProposedChangesArtifactsThreads";
import { AddComment } from "@/entities/proposed-changes/ui/conversations/add-comment";
import { Thread } from "@/entities/proposed-changes/ui/conversations/thread";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import "react-diff-view/style/index.css";

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

const findThreadByChange = (threads: any[], change: any, idFrom?: string, idTo?: string) => {
  const isChangeOnLeftSide = !!change?.isDelete;
  const isChangeOnRightSide = !!change?.isInsert;
  const isChangeOnBothSide = !!change?.isNormal;

  return threads.find((thread) => {
    const threadLineNumber = thread?.line_number?.value;
    const threadStorageId = thread?.storage_id?.value;

    const isThreadOnLeftSide = threadStorageId === idFrom;
    if (isChangeOnLeftSide && isThreadOnLeftSide && threadLineNumber === change.lineNumber) {
      return true;
    }

    const isThreadOnRightSide = threadStorageId === idTo;
    if (isChangeOnRightSide && isThreadOnRightSide && threadLineNumber === change.lineNumber) {
      return true;
    }

    return (
      isChangeOnBothSide &&
      ((isThreadOnLeftSide && threadLineNumber === change.oldLineNumber) ||
        (isThreadOnRightSide && threadLineNumber === change.newLineNumber))
    );
  });
};

interface ArtifactContentDiffProps {
  id: string; // required artifact node ID
  itemPrevious?: { storage_id?: string } | null;
  itemNew?: { storage_id?: string } | null;
}

export const ArtifactContentDiff = (props: ArtifactContentDiffProps) => {
  const { itemPrevious, itemNew, id } = props;

  const { proposedChangeId } = useParams();
  const auth = useAuth();
  const [schemaList] = useAtom(nodeSchemasAtom);
  const [isLoading, setIsLoading] = useState(false);
  const [previousFile, setPreviousFile] = useState("");
  const [newFile, setNewFile] = useState("");
  const [displayAddComment, setDisplayAddComment] = useState<any>({});
  const createObject = useCreateObjectMutation();
  const deleteObject = useDeleteObjectMutation();

  if (!id) {
    return <ErrorScreen message="Missing artifact ID for thread context." />;
  }

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT);

  const queryString =
    schemaData && proposedChangeId
      ? getProposedChangesArtifactsThreads({
          id: proposedChangeId,
          kind: schemaData?.kind,
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

  const fetchFileDetails = useCallback(async (storageId: string, setState: Function) => {
    if (!storageId) return;

    setIsLoading(true);

    try {
      const url = CONFIG.ARTIFACTS_CONTENT_URL(storageId);

      const fileResult = await fetchStream(url);

      setState(fileResult || "");
    } catch (err) {
      console.error("Error while loading files diff: ", err);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading files diff" />);
    }

    setIsLoading(false);
  }, []);

  const setFileDetailsInState = useCallback(async () => {
    await fetchFileDetails(itemPrevious?.storage_id, setPreviousFile);
    await fetchFileDetails(itemNew?.storage_id, setNewFile);
  }, []);

  useEffect(() => {
    setFileDetailsInState();
  }, []);

  const handleCloseComment = () => {
    setDisplayAddComment({});
  };

  const handleSubmitComment = async ({ comment }: { comment: string }) => {
    if (!comment || !approverId || !id) {
      return;
    }

    const newDate = formatISO(new Date());

    const lineNumber = displayAddComment.isNormal
      ? displayAddComment.side === "new"
        ? displayAddComment.newLineNumber
        : displayAddComment.oldLineNumber
      : displayAddComment.lineNumber;

    const newThread = {
      change: {
        id: proposedChangeId,
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
      line_number: {
        value: lineNumber,
      },
      storage_id: {
        value: displayAddComment.side === "new" ? itemNew?.storage_id : itemPrevious?.storage_id,
      },
      artifact_id: {
        value: id,
      },
    };

    await createObject.mutateAsync(
      {
        objectKind: PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT,
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

                console.error("An error occurred while creating the comment:", error);

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

      const thread = findThreadByChange(
        threads,
        change,
        itemPrevious?.storage_id,
        itemNew?.storage_id
      );

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

    const thread = findThreadByChange(
      threads,
      change,
      itemPrevious?.storage_id,
      itemNew?.storage_id
    );

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
    return <ErrorScreen message="Something went wrong when fetching the artifact content." />;
  }

  if (!previousFile && !newFile) {
    return null;
  }

  const diff = formatLines(diffLines(previousFile, newFile), {
    context: 3,
    aname: itemPrevious?.storage_id,
    bname: itemNew?.storage_id,
  });

  const [fileContent] = parseDiff(appendGitDiffHeaderIfNeeded(diff), {
    nearbySequences: "zip",
  });

  return (
    <div className={"pr-2 pb-2"} data-cy="artifact-content-diff">
      <div className="flex">
        <div className="flex-1">
          {itemPrevious?.storage_id && (
            <span className="font-normal italic">Storage id: {itemPrevious?.storage_id}</span>
          )}
        </div>

        <div className="flex-1">
          {itemNew?.storage_id && (
            <span className="font-normal italic">Storage id: {itemNew?.storage_id}</span>
          )}
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
    </div>
  );
};
