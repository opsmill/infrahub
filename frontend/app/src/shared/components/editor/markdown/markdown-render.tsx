import "@/app/styles/markdown.css";

import React from "react";
import Markdown, { type Components } from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { MermaidDiagram } from "@/shared/components/editor/markdown/mermaid-diagram";
import { classNames } from "@/shared/utils/common";

const remarkPlugins = [remarkGfm, remarkBreaks];

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

    return <MermaidDiagram source={source} />;
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
