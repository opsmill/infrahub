import "@/app/styles/markdown.css";

import { type FC, lazy, Suspense } from "react";
import { ErrorBoundary } from "react-error-boundary";
import Markdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { classNames } from "@/shared/utils/common";

const MarkdownWithMermaid = lazy(() => import("./markdown-with-mermaid"));

// Heuristic gate: matches backtick ```mermaid fences (tilde/indented fences not
// covered). A false positive only costs a wasted lazy chunk load, not correctness.
const MERMAID_FENCE = /```\s*mermaid/i;

const remarkPlugins = [remarkGfm, remarkBreaks];

type MarkdownRenderProps = {
  className?: string;
  markdownText?: string;
};

export const MarkdownRender: FC<MarkdownRenderProps> = ({ className = "", markdownText = "" }) => {
  const baseMarkdown = <Markdown remarkPlugins={remarkPlugins}>{markdownText}</Markdown>;

  return (
    <div className={classNames("markdown", className)}>
      {MERMAID_FENCE.test(markdownText) ? (
        <ErrorBoundary fallback={baseMarkdown} resetKeys={[markdownText]}>
          <Suspense fallback={baseMarkdown}>
            <MarkdownWithMermaid markdownText={markdownText} fallback={baseMarkdown} />
          </Suspense>
        </ErrorBoundary>
      ) : (
        baseMarkdown
      )}
    </div>
  );
};
