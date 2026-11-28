import type { ChangeData } from "react-diff-view";
import { describe, expect, it } from "vitest";

import {
  type DiffSide,
  findLineThread,
  getCommentLineNumber,
  isLineSelected,
} from "@/entities/diff/ui/content-diff/line-comments";

const insertChange = (lineNumber: number): ChangeData => ({
  type: "insert",
  isInsert: true,
  lineNumber,
  content: "added",
});

const deleteChange = (lineNumber: number): ChangeData => ({
  type: "delete",
  isDelete: true,
  lineNumber,
  content: "removed",
});

const normalChange = (oldLineNumber: number, newLineNumber: number): ChangeData => ({
  type: "normal",
  isNormal: true,
  oldLineNumber,
  newLineNumber,
  content: "unchanged",
});

interface TestThread {
  id: string;
  line_number: { value: number };
  side: DiffSide | null;
}

const generateThread = (side: DiffSide | null, lineNumber: number): TestThread => ({
  id: `${side}-${lineNumber}`,
  line_number: { value: lineNumber },
  side,
});

const isThreadOnSide = (thread: TestThread, side: DiffSide) => thread.side === side;

describe("getCommentLineNumber", () => {
  it.each([
    {
      name: "a normal change on the new side",
      side: "new",
      change: normalChange(4, 6),
      lineNumber: 6,
    },
    {
      name: "a normal change on the old side",
      side: "old",
      change: normalChange(4, 6),
      lineNumber: 4,
    },
    { name: "an inserted change", side: "new", change: insertChange(9), lineNumber: 9 },
    { name: "a deleted change", side: "old", change: deleteChange(7), lineNumber: 7 },
  ] as const)("returns the line number of $name", ({ side, change, lineNumber }) => {
    // GIVEN
    const selectedSide: DiffSide = side;

    // WHEN
    const result = getCommentLineNumber(selectedSide, change);

    // THEN
    expect(result).toBe(lineNumber);
  });
});

describe("isLineSelected", () => {
  it("returns false when no line is selected", () => {
    // GIVEN
    const change = insertChange(3);

    // WHEN
    const result = isLineSelected(null, change);

    // THEN
    expect(result).toBe(false);
  });

  it.each([
    { name: "an inserted line", side: "new", selected: insertChange(3), change: insertChange(3) },
    { name: "a deleted line", side: "old", selected: deleteChange(3), change: deleteChange(3) },
    {
      name: "a normal line selected on the new side",
      side: "new",
      selected: normalChange(2, 5),
      change: normalChange(2, 5),
    },
    {
      name: "a normal line selected on the old side",
      side: "old",
      selected: normalChange(2, 5),
      change: normalChange(2, 5),
    },
  ] as const)("matches $name", ({ side, selected, change }) => {
    // GIVEN
    const selection = { side, change: selected };

    // WHEN
    const result = isLineSelected(selection, change);

    // THEN
    expect(result).toBe(true);
  });

  it.each([
    {
      name: "a deleted line with the number of the selected inserted line",
      side: "new",
      selected: insertChange(3),
      change: deleteChange(3),
    },
    {
      name: "a normal line whose new number equals the selected inserted line",
      side: "new",
      selected: insertChange(3),
      change: normalChange(1, 3),
    },
    {
      name: "another inserted line",
      side: "new",
      selected: insertChange(3),
      change: insertChange(4),
    },
    {
      name: "another normal line",
      side: "old",
      selected: normalChange(2, 5),
      change: normalChange(3, 6),
    },
  ] as const)("does not match $name", ({ side, selected, change }) => {
    // GIVEN
    const selection = { side, change: selected };

    // WHEN
    const result = isLineSelected(selection, change);

    // THEN
    expect(result).toBe(false);
  });
});

describe("findLineThread", () => {
  it("matches a deleted line with a thread on the old side at its line number", () => {
    // GIVEN
    const threads = [generateThread("new", 4), generateThread("old", 4)];

    // WHEN
    const result = findLineThread(threads, deleteChange(4), isThreadOnSide);

    // THEN
    expect(result).toBe(threads[1]);
  });

  it("matches an inserted line with a thread on the new side at its line number", () => {
    // GIVEN
    const threads = [generateThread("old", 4), generateThread("new", 4)];

    // WHEN
    const result = findLineThread(threads, insertChange(4), isThreadOnSide);

    // THEN
    expect(result).toBe(threads[1]);
  });

  it.each([
    { side: "old", lineNumber: 2 },
    { side: "new", lineNumber: 5 },
  ] as const)(
    "matches a normal line with a thread on the $side side at line $lineNumber",
    ({ side, lineNumber }) => {
      // GIVEN
      const threads = [generateThread(side, lineNumber)];

      // WHEN
      const result = findLineThread(threads, normalChange(2, 5), isThreadOnSide);

      // THEN
      expect(result).toBe(threads[0]);
    }
  );

  it.each([
    { name: "a thread on the new side", thread: generateThread("new", 4) },
    { name: "a thread on neither side", thread: generateThread(null, 4) },
    { name: "a thread on another line", thread: generateThread("old", 5) },
  ])("does not match a deleted line with $name", ({ thread }) => {
    // GIVEN
    const threads = [thread];

    // WHEN
    const result = findLineThread(threads, deleteChange(4), isThreadOnSide);

    // THEN
    expect(result).toBeUndefined();
  });
});
