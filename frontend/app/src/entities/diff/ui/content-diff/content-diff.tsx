import { Button, Tooltip } from "@infrahub/ui";
import { ArrowDownFromLine, ArrowUpFromLine, UnfoldVertical } from "lucide-react";
import { type ReactElement, type ReactNode, useState } from "react";
import {
  Decoration,
  Diff,
  expandFromRawCode,
  Hunk,
  type HunkData,
  parseDiff,
  type RenderGutter,
} from "react-diff-view";
import sha from "sha1";
import { diffAsText } from "unidiff";

import { Col } from "@/shared/components/container";

import {
  type CollapsedLines,
  countLines,
  EXPAND_LINES_STEP,
  type ExpandAction,
  getCollapsedLinesAfter,
  getCollapsedLinesBefore,
  getExpandActions,
  type LineRange,
} from "@/entities/diff/ui/content-diff/collapsed-lines";

import "react-diff-view/style/index.css";

// The parser only reads a diff that starts with a git header.
const GIT_DIFF_HEADER = "diff --git a/content b/content";

const EXPAND_ICONS = {
  up: ArrowUpFromLine,
  down: ArrowDownFromLine,
  all: UnfoldVertical,
};

const getExpandLabel = ({ direction, range: [start, end] }: ExpandAction) => {
  if (direction === "all") {
    return `Expand ${end - start} hidden ${end - start === 1 ? "line" : "lines"}`;
  }

  return `Expand ${EXPAND_LINES_STEP} lines ${direction}`;
};

const getHunkHeader = ({ oldStart, oldLines, newStart, newLines }: HunkData) =>
  `@@ -${oldStart},${oldLines} +${newStart},${newLines} @@`;

interface CollapsedLinesDecorationProps {
  collapsedLines: CollapsedLines;
  header?: string;
  onExpand: (range: LineRange) => void;
}

function CollapsedLinesDecoration({
  collapsedLines,
  header,
  onExpand,
}: CollapsedLinesDecorationProps) {
  return (
    // The library stylesheet is unlayered, so its cell padding and alignment beat plain utilities.
    <Decoration
      className="bg-sky-50"
      gutterClassName="bg-sky-100 p-0!"
      contentClassName="px-2! align-middle! text-neutral-600"
    >
      <Col className="gap-0">
        {getExpandActions(collapsedLines).map((action) => {
          const Icon = EXPAND_ICONS[action.direction];
          const label = getExpandLabel(action);

          return (
            <Tooltip key={action.direction} message={label}>
              <Button
                variant="ghost"
                size="xxs"
                aria-label={label}
                className="h-5 w-full rounded-none text-sky-800"
                onPress={() => onExpand(action.range)}
              >
                <Icon />
              </Button>
            </Tooltip>
          );
        })}
      </Col>
      <span>{header}</span>
    </Decoration>
  );
}

interface ContentDiffProps {
  previousContent: string;
  newContent: string;
  renderGutter: RenderGutter;
  getWidgets: (hunks: HunkData[]) => Record<string, ReactNode>;
}

function ContentDiffView({
  previousContent,
  newContent,
  renderGutter,
  getWidgets,
}: ContentDiffProps) {
  const [expandedRanges, setExpandedRanges] = useState<LineRange[]>([]);

  const previousLines = previousContent.split("\n");
  const previousLineCount = countLines(previousContent);
  const diff = diffAsText(previousContent, newContent, { context: 3 });
  const [file] = parseDiff(`${GIT_DIFF_HEADER}\n${diff}`, { nearbySequences: "zip" });
  const hunks = expandedRanges.reduce(
    (currentHunks, [start, end]) => expandFromRawCode(currentHunks, previousLines, start, end),
    file?.hunks ?? []
  );

  const handleExpand = (range: LineRange) => {
    setExpandedRanges((ranges) => [...ranges, range]);
  };

  const renderHunks = (renderedHunks: HunkData[]) => {
    const elements: ReactElement[] = [];

    renderedHunks.forEach((hunk, index) => {
      const header = getHunkHeader(hunk);
      const collapsedLines = getCollapsedLinesBefore(hunk, renderedHunks[index - 1]);

      if (collapsedLines) {
        elements.push(
          <CollapsedLinesDecoration
            key={`collapsed-${header}`}
            collapsedLines={collapsedLines}
            header={header}
            onExpand={handleExpand}
          />
        );
      }

      elements.push(<Hunk key={header} hunk={hunk} />);
    });

    const trailingLines = getCollapsedLinesAfter(renderedHunks, previousLineCount);
    if (trailingLines) {
      elements.push(
        <CollapsedLinesDecoration
          key="collapsed-trailing"
          collapsedLines={trailingLines}
          onExpand={handleExpand}
        />
      );
    }

    return elements;
  };

  return (
    <Diff
      hunks={hunks}
      viewType="split"
      diffType={file?.type ?? "modify"}
      renderGutter={renderGutter}
      widgets={getWidgets(hunks)}
      optimizeSelection
    >
      {renderHunks}
    </Diff>
  );
}

export function ContentDiff(props: ContentDiffProps) {
  // Expanded ranges are line numbers of one pair of contents, so a new pair starts collapsed.
  return (
    <ContentDiffView key={`${sha(props.previousContent)}${sha(props.newContent)}`} {...props} />
  );
}
