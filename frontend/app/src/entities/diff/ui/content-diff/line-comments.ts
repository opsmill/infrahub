import { type ChangeData, type GutterOptions, isDelete, isNormal } from "react-diff-view";

export type DiffSide = GutterOptions["side"];

export interface LineSelection {
  side: DiffSide;
  change: ChangeData;
}

export interface LineThread {
  id: string;
  line_number?: { value?: number | null } | null;
}

export type IsThreadOnSide<TThread extends LineThread> = (
  thread: TThread,
  side: DiffSide
) => boolean;

/** Line number a comment on this side of the change is stored with. */
export const getCommentLineNumber = (side: DiffSide, change: ChangeData): number => {
  if (isNormal(change)) {
    return side === "new" ? change.newLineNumber : change.oldLineNumber;
  }

  return change.lineNumber;
};

export const isLineSelected = (selection: LineSelection | null, change: ChangeData): boolean => {
  if (!selection || selection.change.type !== change.type) {
    return false;
  }

  return (
    getCommentLineNumber(selection.side, selection.change) ===
    getCommentLineNumber(selection.side, change)
  );
};

export const findLineThread = <TThread extends LineThread>(
  threads: TThread[],
  change: ChangeData,
  isThreadOnSide: IsThreadOnSide<TThread>
): TThread | undefined =>
  threads.find((thread) => {
    const threadLineNumber = thread.line_number?.value;

    if (isNormal(change)) {
      return (
        (isThreadOnSide(thread, "old") && threadLineNumber === change.oldLineNumber) ||
        (isThreadOnSide(thread, "new") && threadLineNumber === change.newLineNumber)
      );
    }

    const side = isDelete(change) ? "old" : "new";
    return isThreadOnSide(thread, side) && threadLineNumber === change.lineNumber;
  });
