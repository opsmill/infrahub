import type { HunkData } from "react-diff-view";
import { describe, expect, it } from "vitest";

import {
  type CollapsedLines,
  countLines,
  getCollapsedLinesAfter,
  getCollapsedLinesBefore,
  getExpandActions,
} from "@/entities/diff/ui/content-diff/collapsed-lines";

const generateHunk = (oldStart: number, oldLines: number): HunkData => ({
  content: `@@ -${oldStart},${oldLines} +${oldStart},${oldLines} @@`,
  oldStart,
  oldLines,
  newStart: oldStart,
  newLines: oldLines,
  changes: [],
});

describe("countLines", () => {
  it("ignores the newline that ends the content", () => {
    // GIVEN
    const content = "first\nsecond\n";

    // WHEN
    const result = countLines(content);

    // THEN
    expect(result).toBe(2);
  });

  it("counts the last line when the content has no final newline", () => {
    // GIVEN
    const content = "first\nsecond";

    // WHEN
    const result = countLines(content);

    // THEN
    expect(result).toBe(2);
  });

  it("returns 0 for an empty content", () => {
    // GIVEN
    const content = "";

    // WHEN
    const result = countLines(content);

    // THEN
    expect(result).toBe(0);
  });
});

describe("getCollapsedLinesBefore", () => {
  it("returns the lines between the previous hunk and the hunk", () => {
    // GIVEN
    const previousHunk = generateHunk(138, 7);
    const hunk = generateHunk(181, 6);

    // WHEN
    const result = getCollapsedLinesBefore(hunk, previousHunk);

    // THEN
    expect(result).toEqual({ range: [145, 181], hasHunkAbove: true, hasHunkBelow: true });
  });

  it("returns the lines from the start of the file for the first hunk", () => {
    // GIVEN
    const hunk = generateHunk(8, 6);

    // WHEN
    const result = getCollapsedLinesBefore(hunk, undefined);

    // THEN
    expect(result).toEqual({ range: [1, 8], hasHunkAbove: false, hasHunkBelow: true });
  });

  it("returns null when the hunk starts right after the previous one", () => {
    // GIVEN
    const previousHunk = generateHunk(1, 6);
    const hunk = generateHunk(7, 6);

    // WHEN
    const result = getCollapsedLinesBefore(hunk, previousHunk);

    // THEN
    expect(result).toBeNull();
  });

  it("returns null when the first hunk starts at the first line", () => {
    // GIVEN
    const hunk = generateHunk(1, 6);

    // WHEN
    const result = getCollapsedLinesBefore(hunk, undefined);

    // THEN
    expect(result).toBeNull();
  });
});

describe("getCollapsedLinesAfter", () => {
  it("returns the lines between the last hunk and the end of the file", () => {
    // GIVEN
    const hunks = [generateHunk(8, 6), generateHunk(40, 7)];

    // WHEN
    const result = getCollapsedLinesAfter(hunks, 60);

    // THEN
    expect(result).toEqual({ range: [47, 61], hasHunkAbove: true, hasHunkBelow: false });
  });

  it("returns null when the last hunk reaches the end of the file", () => {
    // GIVEN
    const hunks = [generateHunk(54, 7)];

    // WHEN
    const result = getCollapsedLinesAfter(hunks, 60);

    // THEN
    expect(result).toBeNull();
  });

  it("returns null for an added file", () => {
    // GIVEN
    const hunks = [generateHunk(0, 0)];

    // WHEN
    const result = getCollapsedLinesAfter(hunks, 0);

    // THEN
    expect(result).toBeNull();
  });

  it("returns null without hunks", () => {
    // GIVEN
    const hunks: HunkData[] = [];

    // WHEN
    const result = getCollapsedLinesAfter(hunks, 60);

    // THEN
    expect(result).toBeNull();
  });
});

describe("getExpandActions", () => {
  it("expands all the lines at once when they fit in one step", () => {
    // GIVEN
    const collapsedLines: CollapsedLines = {
      range: [14, 34],
      hasHunkAbove: true,
      hasHunkBelow: true,
    };

    // WHEN
    const result = getExpandActions(collapsedLines);

    // THEN
    expect(result).toEqual([{ direction: "all", range: [14, 34] }]);
  });

  it("expands one step down from the hunk above and one step up from the hunk below", () => {
    // GIVEN
    const collapsedLines: CollapsedLines = {
      range: [145, 181],
      hasHunkAbove: true,
      hasHunkBelow: true,
    };

    // WHEN
    const result = getExpandActions(collapsedLines);

    // THEN
    expect(result).toEqual([
      { direction: "down", range: [145, 165] },
      { direction: "up", range: [161, 181] },
    ]);
  });

  it("only expands up above the first hunk", () => {
    // GIVEN
    const collapsedLines: CollapsedLines = {
      range: [1, 50],
      hasHunkAbove: false,
      hasHunkBelow: true,
    };

    // WHEN
    const result = getExpandActions(collapsedLines);

    // THEN
    expect(result).toEqual([{ direction: "up", range: [30, 50] }]);
  });

  it("only expands down below the last hunk", () => {
    // GIVEN
    const collapsedLines: CollapsedLines = {
      range: [47, 100],
      hasHunkAbove: true,
      hasHunkBelow: false,
    };

    // WHEN
    const result = getExpandActions(collapsedLines);

    // THEN
    expect(result).toEqual([{ direction: "down", range: [47, 67] }]);
  });
});
