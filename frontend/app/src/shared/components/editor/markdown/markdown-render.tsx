import "@/app/styles/markdown.css";

import { Spinner } from "@infrahub/ui";
import React from "react";
import { ErrorBoundary } from "react-error-boundary";
import Markdown, { type Components } from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { classNames } from "@/shared/utils/common";

const MarkdownWithMermaid = React.lazy(() => import("./markdown-with-mermaid"));

export const remarkPlugins = [remarkGfm, remarkBreaks];

type MarkdownRenderProps = {
  className?: string;
  markdownText?: string;
};

export function MarkdownRender({ className = "", markdownText = "" }: MarkdownRenderProps) {
  const baseMarkdown = <Markdown remarkPlugins={remarkPlugins}>{markdownText}</Markdown>;
  const loadingFallback = (
    <Markdown remarkPlugins={remarkPlugins} components={loadingComponents}>
      {markdownText}
    </Markdown>
  );

  return (
    <div className={classNames("markdown", className)}>
      {/```\s*mermaid/i.test(markdownText) ? (
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
}

// Fallback rendering shown while the diagram is loading:
// render the Markdown normally but replace the raw ```mermaid block with a spinner so the rest of the document stays visible.
const loadingComponents: Components = {
  code({ className, children, ...props }) {
    if (className?.includes("language-mermaid")) {
      return <Spinner className="mx-auto h-40" />;
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
};
