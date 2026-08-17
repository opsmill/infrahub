import type React from "react";
import { useMemo } from "react";
import type { Components, Options } from "react-markdown";
import { MarkdownHooks } from "react-markdown";
import rehypeMermaid, { type RehypeMermaidOptions } from "rehype-mermaid";

import { remarkPlugins } from "@/shared/components/editor/markdown/markdown-render";
import { MermaidDiagram } from "@/shared/components/editor/markdown/mermaid-diagram";
import { type ResolvedTheme, useResolvedTheme } from "@/shared/hooks/use-resolved-theme";

const mermaidThemeFor = (theme: ResolvedTheme) => (theme === "dark" ? "dark" : "default");

const rehypeMermaidOptions = (theme: ResolvedTheme): RehypeMermaidOptions => ({
  strategy: "inline-svg",
  mermaidConfig: { securityLevel: "strict", theme: mermaidThemeFor(theme) },
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
});

// Wrap the rendered mermaid <svg> in a pan/zoom container with controls.
const components: Components = { svg: MermaidDiagram };

type MarkdownWithMermaidProps = {
  markdownText: string;
  fallback: React.ReactNode;
};

export default function MarkdownWithMermaid({ markdownText, fallback }: MarkdownWithMermaidProps) {
  const theme = useResolvedTheme();
  // Mermaid bakes colors into the SVG it emits, so a theme change has to re-run the pipeline. Keying
  // the plugin array on the resolved theme alone is what bounds that: a fresh array on every render
  // would re-render every diagram continuously.
  const rehypePlugins = useMemo<Options["rehypePlugins"]>(
    () => [[rehypeMermaid, rehypeMermaidOptions(theme)]],
    [theme]
  );

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
