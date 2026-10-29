import Markdown, { type Components } from "react-markdown";

import {
  getMermaidSource,
  remarkPlugins,
} from "@/shared/components/editor/markdown/markdown-render";
import { MermaidDiagram } from "@/shared/components/editor/markdown/mermaid-diagram";

const components: Components = {
  pre({ node: _node, children, ...props }) {
    const source = getMermaidSource(children);
    if (source !== null) return <MermaidDiagram source={source} />;
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
