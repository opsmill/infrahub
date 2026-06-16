import "@/app/styles/markdown.css";

import { Spinner } from "@infrahub/ui";
import React from "react";
import { ErrorBoundary } from "react-error-boundary";
import Markdown, { type Components } from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { classNames } from "@/shared/utils/common";

const MarkdownWithMermaid = React.lazy(() => import("./markdown-with-mermaid"));

// Heuristic gate: matches backtick ```mermaid fences (tilde/indented fences not
// covered). A false positive only costs a wasted lazy chunk load, not correctness.
const MERMAID_FENCE = /```\s*mermaid/i;

const remarkPlugins = [remarkGfm, remarkBreaks];

// Fallback rendering shown while the diagram is loading: render the markdown
// normally but replace the raw ```mermaid block with a spinner where the
// diagram will appear, so the rest of the document stays visible.
const loadingComponents: Components = {
  code({ node: _node, className: codeClassName, children, ...props }) {
    if (codeClassName?.includes("language-mermaid")) {
      return <Spinner className="mx-auto h-40" />;
    }
    return (
      <code className={codeClassName} {...props}>
        {children}
      </code>
    );
  },
};

type MarkdownRenderProps = {
  className?: string;
  markdownText?: string;
};

export const MarkdownRender: React.FC<MarkdownRenderProps> = ({
  className = "",
  markdownText = "",
}) => {
  const baseMarkdown = <Markdown remarkPlugins={remarkPlugins}>{markdownText}</Markdown>;
  const loadingFallback = (
    <Markdown remarkPlugins={remarkPlugins} components={loadingComponents}>
      {markdownText}
    </Markdown>
  );

  return (
    <div className={classNames("markdown", className)}>
      {MERMAID_FENCE.test(markdownText) ? (
        <ErrorBoundary fallback={baseMarkdown} resetKeys={[markdownText]}>
          <React.Suspense fallback={loadingFallback}>
            <MarkdownWithMermaid markdownText={markdownText} fallback={loadingFallback} />
          </React.Suspense>
        </ErrorBoundary>
      ) : (
        baseMarkdown
      )}
    </div>
  );
};
