import mermaid from "mermaid";
import type React from "react";
import type { Options } from "react-markdown";
import { MarkdownHooks } from "react-markdown";
import rehypeMermaid, { type RehypeMermaidOptions } from "rehype-mermaid";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

type PluggableList = NonNullable<Options["rehypePlugins"]>;

const remarkPlugins: PluggableList = [remarkGfm, remarkBreaks];

const rehypeMermaidOptions: RehypeMermaidOptions = {
  strategy: "inline-svg",
  mermaidConfig: { securityLevel: "strict", theme: "default" },
  // Show the raw diagram source on failure instead of mermaid's error graphic.
  errorFallback: (_element, diagram) => ({
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
  }),
};

const rehypePlugins: PluggableList = [[rehypeMermaid, rehypeMermaidOptions]];

// mermaid-isomorphic's browser renderer calls mermaid.render() but never
// mermaid.initialize(), so the mermaidConfig passed to rehype-mermaid is ignored
// client-side. Initialize the shared mermaid singleton directly so strict
// sanitization is enforced (not left to mermaid's default) and the theme applies.
mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "default" });

type MarkdownWithMermaidProps = {
  markdownText: string;
  fallback: React.ReactNode;
};

export default function MarkdownWithMermaid({ markdownText, fallback }: MarkdownWithMermaidProps) {
  return (
    <MarkdownHooks remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins} fallback={fallback}>
      {markdownText}
    </MarkdownHooks>
  );
}
