import { type ResolvedTheme, useResolvedTheme } from "@infrahub/ui";
import mermaid from "mermaid";
import type React from "react";
import { useMemo } from "react";
import type { Components, Options } from "react-markdown";
import { MarkdownHooks } from "react-markdown";
import rehypeMermaid, { type RehypeMermaidOptions } from "rehype-mermaid";

import { remarkPlugins } from "@/shared/components/editor/markdown/markdown-render";
import { MermaidDiagram } from "@/shared/components/editor/markdown/mermaid-diagram";

const rehypeMermaidOptions: RehypeMermaidOptions = {
  strategy: "inline-svg",
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

// Wrap the rendered mermaid <svg> in a pan/zoom container with controls.
const components: Components = { svg: MermaidDiagram };

/**
 * Configures mermaid for the diagrams about to render. The renderer's browser build calls
 * `mermaid.render` against mermaid's global configuration and ignores the rehype plugin's
 * `mermaidConfig` — its documentation says to call `mermaid.initialize()` manually, which reaches
 * the same module instance. A diagram's own `%%{init}%%` directive or front matter still wins, by
 * mermaid's own precedence.
 *
 * Shaped as a rehype plugin so the call is part of the pipeline itself, sequenced before the
 * rendering plugin. A render-phase call in the component would be at the React Compiler's mercy
 * (it may drop a memoized expression whose result is unused), and an effect would race the child's
 * async processing.
 *
 * ⚠ The version range in package.json must stay compatible with the one `mermaid-isomorphic`
 * declares, or the tree would hold two mermaid instances and this would configure the one the
 * renderer does not use.
 */
function rehypeConfigureMermaid({ theme }: { theme: ResolvedTheme }) {
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    theme: theme === "dark" ? "dark" : "default",
  });
}

type MarkdownWithMermaidProps = {
  markdownText: string;
  fallback: React.ReactNode;
};

export default function MarkdownWithMermaid({ markdownText, fallback }: MarkdownWithMermaidProps) {
  const theme = useResolvedTheme();

  const rehypePlugins: Options["rehypePlugins"] = useMemo(
    () => [
      [rehypeConfigureMermaid, { theme }],
      [rehypeMermaid, rehypeMermaidOptions],
    ],
    [theme]
  );

  // Mermaid bakes colors into the SVG it emits, and the source text does not change on a theme
  // flip — remounting on the theme is what forces the pipeline to run again.
  return (
    <MarkdownHooks
      key={theme}
      remarkPlugins={remarkPlugins}
      rehypePlugins={rehypePlugins}
      components={components}
      fallback={fallback}
    >
      {markdownText}
    </MarkdownHooks>
  );
}
