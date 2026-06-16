import type React from "react";
import type { Components, Options } from "react-markdown";
import { MarkdownHooks } from "react-markdown";
import rehypeMermaid, { type RehypeMermaidOptions } from "rehype-mermaid";

import { remarkPlugins } from "@/shared/components/editor/markdown/markdown-render";
import { MermaidDiagram } from "@/shared/components/editor/markdown/mermaid-diagram";

const rehypeMermaidOptions: RehypeMermaidOptions = {
  strategy: "inline-svg",
  mermaidConfig: { securityLevel: "strict", theme: "default" },
  // On failure, show a red error banner with the message above the raw diagram
  errorFallback: (_element, diagram, error) => {
    const message = error instanceof Error ? error.message : String(error);
    return {
      type: "element",
      tagName: "div",
      properties: {},
      children: [
        {
          type: "element",
          tagName: "div",
          properties: { className: ["mermaid-error", "text-sm rounded-md p-2"] },
          children: [{ type: "text", value: message }],
        },
        {
          type: "element",
          tagName: "pre",
          properties: {},
          children: [
            {
              type: "element",
              tagName: "code",
              properties: {},
              children: [{ type: "text", value: diagram }],
            },
          ],
        },
      ],
    };
  },
};

const rehypePlugins: Options["rehypePlugins"] = [[rehypeMermaid, rehypeMermaidOptions]];

// Wrap the rendered mermaid <svg> in a pan/zoom container with controls.
const components: Components = { svg: MermaidDiagram };

type MarkdownWithMermaidProps = {
  markdownText: string;
  fallback: React.ReactNode;
};

export default function MarkdownWithMermaid({ markdownText, fallback }: MarkdownWithMermaidProps) {
  return (
    <MarkdownHooks
      remarkPlugins={remarkPlugins}
      rehypePlugins={rehypePlugins}
      components={components}
      fallback={fallback}
    >
      {markdownText}
    </MarkdownHooks>
  );
}
