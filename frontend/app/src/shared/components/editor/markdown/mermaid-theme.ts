import type { ResolvedTheme } from "@/shared/hooks/use-resolved-theme";

const MERMAID_FENCE = /(^|\n)([ \t]*)(`{3,}|~{3,})[ \t]*mermaid[^\n]*\n/g;

// A diagram that already configures itself, by directive or by YAML front matter, is left alone.
const CONFIGURES_ITSELF = /^\s*(%%\{|---[ \t]*\n)/;

// Mermaid honours a per-diagram directive even when it has not been configured globally, which is
// what makes this work: the browser build of the renderer never calls mermaid.initialize, so the
// mermaidConfig passed to the rehype plugin is silently discarded and the diagram source is the
// only channel left for a theme.
const themeDirective = (theme: ResolvedTheme) =>
  `%%{init: {"theme":"${theme === "dark" ? "dark" : "default"}"}}%%`;

/**
 * Applies a theme to every mermaid block in a markdown document by prefixing each diagram with an
 * init directive, returning the document unchanged when there is nothing to theme.
 *
 * Rewrites only the copy handed to the renderer — the stored document keeps whatever the author
 * wrote, so a theme change never edits a user's content.
 */
export function withMermaidTheme(markdown: string, theme: ResolvedTheme): string {
  if (!markdown.includes("mermaid")) {
    return markdown;
  }

  return markdown.replace(
    MERMAID_FENCE,
    (match, lead: string, indent: string, fence: string, offset: number) => {
      const body = markdown.slice(offset + match.length);
      if (CONFIGURES_ITSELF.test(body)) {
        return match;
      }
      return `${lead}${indent}${fence}mermaid\n${indent}${themeDirective(theme)}\n`;
    }
  );
}
