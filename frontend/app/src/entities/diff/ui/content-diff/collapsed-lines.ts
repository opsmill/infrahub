import type { HunkData } from "react-diff-view";

export const EXPAND_LINES_STEP = 20;

/** Half-open range of line numbers of the previous content: `start` included, `end` excluded. */
export type LineRange = [start: number, end: number];

export interface CollapsedLines {
  range: LineRange;
  hasHunkAbove: boolean;
  hasHunkBelow: boolean;
}

export type ExpandDirection = "up" | "down" | "all";

export interface ExpandAction {
  direction: ExpandDirection;
  range: LineRange;
}

export const countLines = (content: string): number => {
  if (!content) {
    return 0;
  }

  const lines = content.split("\n");
  return lines.at(-1) === "" ? lines.length - 1 : lines.length;
};

export const getCollapsedLinesBefore = (
  hunk: HunkData,
  previousHunk: HunkData | undefined
): CollapsedLines | null => {
  const start = previousHunk ? previousHunk.oldStart + previousHunk.oldLines : 1;

  if (hunk.oldStart <= start) {
    return null;
  }

  return { range: [start, hunk.oldStart], hasHunkAbove: !!previousHunk, hasHunkBelow: true };
};

export const getCollapsedLinesAfter = (
  hunks: HunkData[],
  previousLineCount: number
): CollapsedLines | null => {
  const lastHunk = hunks.at(-1);
  if (!lastHunk) {
    return null;
  }

  // An added file has a single hunk at old line 0, which must not count as a hidden line.
  const start = Math.max(lastHunk.oldStart + lastHunk.oldLines, 1);
  const end = previousLineCount + 1;

  if (end <= start) {
    return null;
  }

  return { range: [start, end], hasHunkAbove: true, hasHunkBelow: false };
};

export const getExpandActions = ({
  range: [start, end],
  hasHunkAbove,
  hasHunkBelow,
}: CollapsedLines): ExpandAction[] => {
  if (end - start <= EXPAND_LINES_STEP) {
    return [{ direction: "all", range: [start, end] }];
  }

  const actions: ExpandAction[] = [];

  if (hasHunkAbove) {
    actions.push({ direction: "down", range: [start, start + EXPAND_LINES_STEP] });
  }

  if (hasHunkBelow) {
    actions.push({ direction: "up", range: [end - EXPAND_LINES_STEP, end] });
  }

  return actions;
};
