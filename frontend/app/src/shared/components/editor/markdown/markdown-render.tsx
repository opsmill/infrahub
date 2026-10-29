import "@/app/styles/markdown.css";

import { Spinner } from "@infrahub/ui";
import React from "react";
import { ErrorBoundary } from "react-error-boundary";
import Markdown, { type Components } from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { DiagramError } from "@/shared/components/editor/markdown/diagram-error";
import { classNames } from "@/shared/utils/common";

const MermaidDiagram = React.lazy(() => import("./mermaid-diagram"));

const remarkPlugins = [remarkGfm, remarkBreaks];

const LOAD_FAILED = "Could not load the diagram. Reload the page to try again.";

function getMermaidSource(preChildren: React.ReactNode): string | null {
  if (!React.isValidElement<{ className?: string; children?: unknown }>(preChildren)) return null;
  const { className, children } = preChildren.props;
  if (!className?.includes("language-mermaid")) return null;
  return String(children ?? "").trimEnd();
}

const components: Components = {
  pre({ node: _node, children, ...props }) {
    const source = getMermaidSource(children);
    if (source === null) return <pre {...props}>{children}</pre>;

    return (
      <ErrorBoundary
        fallback={<DiagramError message={LOAD_FAILED} source={source} />}
        resetKeys={[source]}
      >
        <React.Suspense fallback={<Spinner className="mx-auto h-40" />}>
          <MermaidDiagram source={source} />
        </React.Suspense>
      </ErrorBoundary>
    );
  },
};

interface MarkdownRenderProps {
  className?: string;
  markdownText?: string;
}

export function MarkdownRender({ className = "", markdownText = "" }: MarkdownRenderProps) {
  return (
    <div className={classNames("markdown", className)}>
      <Markdown remarkPlugins={remarkPlugins} components={components}>
        {markdownText}
      </Markdown>
    </div>
  );
}
