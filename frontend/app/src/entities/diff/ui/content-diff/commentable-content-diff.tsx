import { PencilLineIcon } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Button } from "react-aria-components";
import { getChangeKey, type HunkData, type RenderGutter } from "react-diff-view";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { ContentDiff } from "@/entities/diff/ui/content-diff/content-diff";
import {
  type DiffSide,
  findLineThread,
  getCommentLineNumber,
  type IsThreadOnSide,
  isLineSelected,
  type LineSelection,
  type LineThread,
} from "@/entities/diff/ui/content-diff/line-comments";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useDeleteObjectMutation } from "@/entities/nodes/object/ui/queries/delete-object.mutation";
import {
  type PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT,
  type PROPOSED_CHANGES_FILE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "@/entities/proposed-changes/domain/model/proposed-change-thread";
import { AddComment } from "@/entities/proposed-changes/ui/conversations/add-comment";
import { Thread } from "@/entities/proposed-changes/ui/conversations/thread";

interface CommentableContentDiffProps<TThread extends LineThread> {
  previousContent: string;
  newContent: string;
  previousLabel?: string;
  newLabel?: string;
  proposedChangeId?: string;
  threads: TThread[];
  onThreadsChange: () => unknown;
  isThreadOnSide: IsThreadOnSide<TThread>;
  threadKind:
    | typeof PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT
    | typeof PROPOSED_CHANGES_FILE_THREAD_OBJECT;
  buildThreadData: (line: { side: DiffSide; lineNumber: number }) => Record<string, unknown>;
}

export function CommentableContentDiff<TThread extends LineThread>({
  previousContent,
  newContent,
  previousLabel,
  newLabel,
  proposedChangeId,
  threads,
  onThreadsChange,
  isThreadOnSide,
  threadKind,
  buildThreadData,
}: CommentableContentDiffProps<TThread>) {
  const { isAuthenticated } = useAuth();
  const [selectedLine, setSelectedLine] = useState<LineSelection | null>(null);
  const createObject = useCreateObjectMutation();
  const deleteObject = useDeleteObjectMutation();

  const handleCloseComment = () => {
    setSelectedLine(null);
  };

  const handleSubmitComment = async ({ comment }: { comment: string }) => {
    if (!comment || !selectedLine) {
      return;
    }

    const { side } = selectedLine;
    const lineNumber = getCommentLineNumber(side, selectedLine.change);

    await createObject.mutateAsync(
      {
        objectKind: threadKind,
        data: {
          change: {
            id: proposedChangeId,
          },
          resolved: {
            value: false,
          },
          line_number: {
            value: lineNumber,
          },
          ...buildThreadData({ side, lineNumber }),
        },
      },
      {
        onSuccess: async (newThread) => {
          const threadId = newThread.id;

          await createObject.mutateAsync(
            {
              objectKind: PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
              data: {
                text: {
                  value: comment,
                },
                thread: {
                  id: threadId,
                },
              },
            },
            {
              onSuccess: async () => {
                onThreadsChange();
                handleCloseComment();
              },
              onError: async (error) => {
                await deleteObject.mutateAsync({
                  objectKind: threadKind,
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

  const getWidgets = (hunks: HunkData[]) => {
    const widgets: Record<string, ReactNode> = {};

    for (const change of hunks.flatMap((hunk) => hunk.changes)) {
      const changeKey = getChangeKey(change);

      if (isLineSelected(selectedLine, change)) {
        widgets[changeKey] = (
          <AddComment onSubmit={handleSubmitComment} onCancel={handleCloseComment} />
        );
      } else {
        const thread = findLineThread(threads, change, isThreadOnSide);

        if (thread) {
          widgets[changeKey] = <Thread thread={thread} refetch={onThreadsChange} />;
        }
      }
    }

    return widgets;
  };

  const renderGutter: RenderGutter = ({
    renderDefault,
    wrapInAnchor,
    inHoverState,
    side,
    change,
  }) => {
    const thread = findLineThread(threads, change, isThreadOnSide);

    if (thread || !isAuthenticated || !proposedChangeId) {
      return wrapInAnchor(renderDefault());
    }

    return (
      <>
        {wrapInAnchor(renderDefault())}

        {inHoverState && (
          <Button
            aria-label={`Add a comment on line ${getCommentLineNumber(side, change)}`}
            className="absolute top-1/2 left-1/2 z-10 inline-flex w-full -translate-x-1/2 -translate-y-1/2 items-center justify-center bg-surface p-1"
            onClick={() => setSelectedLine({ side, change })}
          >
            <PencilLineIcon className="size-3.5" />
          </Button>
        )}
      </>
    );
  };

  return (
    <>
      <div className="flex">
        <div className="flex-1">
          {previousLabel && <span className="font-normal italic">{previousLabel}</span>}
        </div>

        <div className="flex-1">
          {newLabel && <span className="font-normal italic">{newLabel}</span>}
        </div>
      </div>

      <div className="ml-2 bg-content-muted">
        <ContentDiff
          previousContent={previousContent}
          newContent={newContent}
          renderGutter={renderGutter}
          getWidgets={getWidgets}
        />
      </div>
    </>
  );
}
