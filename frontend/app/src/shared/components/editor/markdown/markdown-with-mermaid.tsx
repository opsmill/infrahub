import { isValidElement } from "react";
import Markdown, { type Components } from "react-markdown";

import { remarkPlugins } from "@/shared/components/editor/markdown/markdown-render";
import { MermaidDiagram } from "@/shared/components/editor/markdown/mermaid-diagram";

const components: Components = {
  pre({ node: _node, children, ...props }) {
    if (isValidElement<{ className?: string; children?: unknown }>(children)) {
      const { className, children: code } = children.props;
      if (className?.includes("language-mermaid")) {
        return <MermaidDiagram source={String(code ?? "").trimEnd()} />;
      }
    }
    return <pre {...props}>{children}</pre>;
  },
};

type MarkdownWithMermaidProps = {
  markdownText: string;
};

export default function MarkdownWithMermaid({ markdownText }: MarkdownWithMermaidProps) {
  return (
    <Markdown remarkPlugins={remarkPlugins} components={components}>
      {markdownText}
    </Markdown>
  );
}
