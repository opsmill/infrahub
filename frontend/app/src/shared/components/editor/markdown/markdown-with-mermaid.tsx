import type React from "react";
import { useMemo } from "react";
import type { Components, Options } from "react-markdown";
import { MarkdownHooks } from "react-markdown";
import rehypeMermaid, { type RehypeMermaidOptions } from "rehype-mermaid";

import { remarkPlugins } from "@/shared/components/editor/markdown/markdown-render";
import { MermaidDiagram } from "@/shared/components/editor/markdown/mermaid-diagram";
import { withMermaidTheme } from "@/shared/components/editor/markdown/mermaid-theme";
import { useResolvedTheme } from "@/shared/hooks/use-resolved-theme";

// mermaidConfig is inert in the browser: the renderer's browser build never calls
// mermaid.initialize, so nothing here reaches mermaid. It is kept because the same options object
// is honoured by the node build. The theme travels through the diagram source instead.
const rehypeMermaidOptions: RehypeMermaidOptions = {
  strategy: "inline-svg",
  mermaidConfig: { securityLevel: "strict" },
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
  const theme = useResolvedTheme();
  // Mermaid bakes colors into the SVG it emits, so a theme change has to re-run the pipeline.
  // Keying the themed source on the theme is what bounds that: a fresh string every render would
  // re-render every diagram continuously.
  const themedMarkdown = useMemo(
    () => withMermaidTheme(markdownText, theme),
    [markdownText, theme]
  );

  return (
    <MarkdownHooks
      remarkPlugins={remarkPlugins}
      rehypePlugins={rehypePlugins}
      components={components}
      fallback={fallback}
    >
      {themedMarkdown}
    </MarkdownHooks>
  );
}
