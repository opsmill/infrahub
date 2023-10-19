import { gql, useReactiveVar } from "@apollo/client";
import { PencilIcon } from "@heroicons/react/24/outline";
import { formatISO } from "date-fns";
import { useAtom } from "jotai";
import { useCallback, useContext, useEffect, useState } from "react";
import { Diff, Hunk, getChangeKey, parseDiff } from "react-diff-view";
import "react-diff-view/style/index.css";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import sha from "sha1";
import { diffLines, formatLines } from "unidiff";
import { ALERT_TYPES, Alert } from "../../../components/alert";
import { Button } from "../../../components/button";
import { AddComment } from "../../../components/conversations/add-comment";
import { Thread } from "../../../components/conversations/thread";
import { CONFIG } from "../../../config/config";
import {
  PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT,
  PROPOSED_CHANGES_FILE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "../../../config/constants";
import { AuthContext } from "../../../decorators/withAuth";
import graphqlClient from "../../../graphql/graphqlClientApollo";
import { createObject } from "../../../graphql/mutations/objects/createObject";
import { deleteObject } from "../../../graphql/mutations/objects/deleteObject";
import { getProposedChangesArtifactsThreads } from "../../../graphql/queries/proposed-changes/getProposedChangesArtifactsThreads";
import { branchVar } from "../../../graphql/variables/branchVar";
import { dateVar } from "../../../graphql/variables/dateVar";
import useQuery from "../../../hooks/useQuery";
import { schemaState } from "../../../state/atoms/schema.atom";
import { fetchStream } from "../../../utils/fetch";
import { stringifyWithoutQuotes } from "../../../utils/string";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";

const fakeIndex = () => {
  return sha(Math.random() * 100000).slice(0, 9);
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

const getThread = (threads: any[], change: any, idFrom?: string, idTo?: string) => {
  const thread = threads.find((thread) => {
    const THREADLineNumber = thread?.line_number?.value;

    if (
      change?.isDelete &&
      THREADLineNumber === change.lineNumber &&
      (thread?.storage_id?.value === idFrom || (!thread?.storage_id?.value && !idFrom))
    ) {
      // Thread on the left side
      return true;
    }

    if (
      change?.isInsert &&
      thread?.storage_id?.value === idTo &&
      THREADLineNumber === change.lineNumber
    ) {
      // Thread on the right side
      return true;
    }

    if (change.isNormal && THREADLineNumber === change.newLineNumber) {
      // Both left + right side
      return true;
    }

    return false;
  });

  return thread;
};

export const ArtifactContentDiff = (props: any) => {
  const { itemPrevious, itemNew } = props;

  const { proposedchange } = useParams();
  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const auth = useContext(AuthContext);
  const [schemaList] = useAtom(schemaState);
  const [isLoading, setIsLoading] = useState(false);
  const [previousFile, setPreviousFile] = useState("");
  const [newFile, setNewFile] = useState("");
  const [displayAddComment, setDisplayAddComment] = useState<any>({});

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT);

  const queryString =
    schemaData && proposedchange
      ? getProposedChangesArtifactsThreads({
          id: proposedchange,
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

  const handleSubmitComment = async (data: any, event: any) => {
    let threadId;

    try {
      event.target.reset();

      if (!data || !approverId) {
        return;
      }

      const newDate = formatISO(new Date());

      const newThread = {
        change: {
          id: proposedchange,
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
          value:
            displayAddComment.lineNumber ||
            displayAddComment.newLineNumber ||
            displayAddComment.oldLineNumber,
        },
        storage_id: {
          value: displayAddComment.side === "new" ? itemNew?.storage_id : itemPrevious?.storage_id,
        },
      };

      const threadMutationString = createObject({
        kind: PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT,
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

      threadId = result?.data[`${PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT}Create`]?.object?.id;

      const newComment = {
        text: {
          value: data.comment,
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

      const commentMutationString = createObject({
        kind: PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
        data: stringifyWithoutQuotes(newComment),
      });

      const commentMutation = gql`
        ${commentMutationString}
      `;

      await graphqlClient.mutate({
        mutation: commentMutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Comment added"} />);

      refetch();

      setIsLoading(false);

      setDisplayAddComment({});
    } catch (error: any) {
      if (threadId) {
        const mutationString = deleteObject({
          name: PROPOSED_CHANGES_FILE_THREAD_OBJECT,
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
        return;
      }

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

  const handleCloseComment = () => {
    setDisplayAddComment({});
  };

  const getWidgets = (hunks: any) => {
    const changes = hunks.reduce((result: any, { changes }: any) => [...result, ...changes], []);

    return changes.reduce((widgets: any, change: any) => {
      const changeKey = getChangeKey(change);

      if (shouldDisplayAddComment(displayAddComment, change)) {
        return {
          ...widgets,
          [changeKey]: <AddComment onSubmit={handleSubmitComment} onClose={handleCloseComment} />,
        };
      }

      const thread = getThread(threads, change, itemPrevious?.storage_id, itemNew?.storage_id);

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
          <div
            key={index}
            className="bg-custom-white p-4 border border-custom-blue-500 rounded-md m-2">
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

    const thread = getThread(threads, change, itemPrevious?.storage_id, itemNew?.storage_id);

    if (thread || !auth?.permissions?.write || !proposedchange) {
      // Do not display the add button if there is already a thread
      return wrapInAnchor(renderDefault());
    }

    return (
      <>
        {wrapInAnchor(renderDefault())}

        {inHoverState && (
          <Button
            className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-10"
            onClick={handleClick}>
            <PencilIcon className="w-3 h-3" />
          </Button>
        )}
      </>
    );
  };

  if (loading || isLoading) {
    return <LoadingScreen />;
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
    <div className={"pr-2 pb-2"}>
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
          optimizeSelection>
          {(hunks) => hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)}
        </Diff>
      </div>
    </div>
  );
};
