import { PencilIcon } from "@heroicons/react/24/outline";
import { Diff, Hunk, getChangeKey, parseDiff } from "react-diff-view";
import "react-diff-view/style/index.css";
import { Button } from "../../../components/button";
import { text as diffText } from "./test";

const comments = [
  {
    oldLineNumber: 47,
    message: "Very interesting comment here",
  },
  {
    lineNumber: 48,
    message: "An interesting comment here",
  },
  {
    lineNumber: 48,
    message: "Again another one",
  },
];

export const FilesDiff = () => {
  const files = parseDiff(diffText);

  const getWidgets = (hunks: any) => {
    const changes = hunks.reduce((result: any, { changes }: any) => [...result, ...changes], []);

    const changesWithComments = changes
      .map((change: any) => {
        const relatedComments = comments.filter(
          (comment: any) =>
            (comment.newLineNumber &&
              change.newLineNumber &&
              comment.newLineNumber === change.newLineNumber) ||
            (comment.oldLineNumber &&
              change.oldLineNumber &&
              comment.oldLineNumber === change.oldLineNumber) ||
            (comment.lineNumber && change.lineNumber && comment.lineNumber === change.lineNumber)
        );

        if (relatedComments?.length) {
          return {
            ...change,
            comments: relatedComments,
          };
        }

        return null;
      })
      .filter(Boolean);

    return changesWithComments.reduce((widgets: any, change: any) => {
      const changeKey = getChangeKey(change);

      if (!change.comments) {
        return widgets;
      }

      return {
        ...widgets,
        [changeKey]: change?.comments?.map((comment: any, index: number) => (
          <div key={index} className="bg-white p-4 border border-blue-500 rounded-md m-2">
            {comment.message}
          </div>
        )),
      };
    }, {});
  };

  const renderGutter = (options: any) => {
    const { renderDefault, wrapInAnchor, inHoverState } = options;

    return (
      <>
        {wrapInAnchor(renderDefault())}

        {inHoverState && (
          <Button className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
            <PencilIcon className="w-3 h-3" />
          </Button>
        )}
      </>
    );
  };

  const renderFile = (options: any) => {
    console.log("options: ", options);
    const { oldPath, oldRevision, newRevision, type, hunks } = options;

    return (
      <div className="p-4 m-4 bg-gray-50">
        <div className="font-semibold">{oldPath}</div>

        <Diff
          key={oldRevision + "-" + newRevision}
          viewType="split"
          diffType={type}
          hunks={hunks}
          renderGutter={renderGutter}
          widgets={getWidgets(hunks)}
          optimizeSelection>
          {(hunks) => hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)}
        </Diff>
      </div>
    );
  };

  return <div className="bg-white">{files.map(renderFile)}</div>;
};
