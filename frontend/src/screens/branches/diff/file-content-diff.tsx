import { PencilIcon } from "@heroicons/react/24/outline";
import { useCallback, useEffect, useState } from "react";
import { Diff, Hunk, getChangeKey, parseDiff } from "react-diff-view";
import "react-diff-view/style/index.css";
import { toast } from "react-toastify";
import sha from "sha1";
import { diffLines, formatLines } from "unidiff";
import { StringParam, useQueryParam } from "use-query-params";
import Accordion from "../../../components/accordion";
import { ALERT_TYPES, Alert } from "../../../components/alert";
import { Button } from "../../../components/button";
import { AddComment } from "../../../components/conversations/add-comment";
import { CONFIG } from "../../../config/config";
import { QSP } from "../../../config/qsp";
import { fetchStream } from "../../../utils/fetch";
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

export const FileContentDiff = (props: any) => {
  const { repositoryId, file, commitFrom, commitTo } = props;

  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);
  const [isLoading, setIsLoading] = useState(false);
  const [previousFile, setPreviousFile] = useState(false);
  const [newFile, setNewFile] = useState(false);
  // const [comments, setComments] = useState([]);
  const [displayAddComment, setDisplayAddComment] = useState<any>({});

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
      console.error("err: ", err);
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

  const handleSubmitComment = () => {
    //
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

    return (
      <>
        {wrapInAnchor(renderDefault())}

        {inHoverState && (
          <Button
            className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2"
            onClick={handleClick}>
            <PencilIcon className="w-3 h-3" />
          </Button>
        )}
      </>
    );
  };

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!previousFile && !newFile) {
    return null;
  }

  const diff = formatLines(diffLines(previousFile, newFile), { context: 3 });

  const [fileContent] = parseDiff(appendGitDiffHeaderIfNeeded(diff), { nearbySequences: "zip" });

  return (
    <div className={"rounded-lg shadow p-4 m-4 bg-custom-white"}>
      <Accordion title={file.location}>
        <div className="flex">
          <div className="flex-1">
            {commitFrom && <span className="font-normal italic">Commit: {commitFrom}</span>}
          </div>

          <div className="flex-1">
            {commitTo && <span className="font-normal italic">Commit: {commitTo}</span>}
          </div>
        </div>

        <div className="bg-gray-50">
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
