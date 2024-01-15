import { gql } from "@apollo/client";
import { PencilIcon } from "@heroicons/react/24/outline";
import { formatISO } from "date-fns";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useCallback, useContext, useEffect, useState } from "react";
import { Diff, Hunk, getChangeKey, parseDiff } from "react-diff-view";
import "react-diff-view/style/index.css";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import sha from "sha1";
import { diffLines, formatLines } from "unidiff";
import { StringParam, useQueryParam } from "use-query-params";
import { Button } from "../../../components/buttons/button";
import { AddComment } from "../../../components/conversations/add-comment";
import { Thread } from "../../../components/conversations/thread";
import Accordion from "../../../components/display/accordion";
import { ALERT_TYPES, Alert } from "../../../components/utils/alert";
import { CONFIG } from "../../../config/config";
import {
  PROPOSED_CHANGES_FILE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "../../../config/constants";
import { QSP } from "../../../config/qsp";
import { AuthContext } from "../../../decorators/withAuth";
import graphqlClient from "../../../graphql/graphqlClientApollo";
import { createObject } from "../../../graphql/mutations/objects/createObject";
import { deleteObject } from "../../../graphql/mutations/objects/deleteObject";
import { getProposedChangesFilesThreads } from "../../../graphql/queries/proposed-changes/getProposedChangesFilesThreads";
import useQuery from "../../../hooks/useQuery";
import { currentBranchAtom } from "../../../state/atoms/branches.atom";
import { schemaState } from "../../../state/atoms/schema.atom";
import { datetimeAtom } from "../../../state/atoms/time.atom";
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

  const { proposedchange } = useParams();
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const auth = useContext(AuthContext);
  const [schemaList] = useAtom(schemaState);
  const [isLoading, setIsLoading] = useState(false);
  const [previousFile, setPreviousFile] = useState(false);
  const [newFile, setNewFile] = useState(false);
  const [displayAddComment, setDisplayAddComment] = useState<any>({});

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_FILE_THREAD_OBJECT);

  const queryString =
    schemaData && proposedchange
      ? getProposedChangesFilesThreads({
          id: proposedchange,
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

  const handleSubmitComment = async ({ comment }: { comment: string }) => {
    let threadId;

    try {
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
          id: proposedchange,
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

      const threadMutationString = createObject({
        kind: PROPOSED_CHANGES_FILE_THREAD_OBJECT,
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

      threadId = result?.data[`${PROPOSED_CHANGES_FILE_THREAD_OBJECT}Create`]?.object?.id;

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

      if (refetch) {
        refetch();
      }

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

    const thread = findThreadByChange(threads, change, commitFrom, commitTo);

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
    <div className={"rounded-lg shadow p-2 m-4 bg-custom-white"}>
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
            optimizeSelection>
            {(hunks) => hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)}
          </Diff>
        </div>
      </Accordion>
    </div>
  );
};
