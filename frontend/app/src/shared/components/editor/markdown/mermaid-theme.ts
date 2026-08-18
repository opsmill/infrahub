import type { ResolvedTheme } from "@/shared/hooks/use-resolved-theme";

const FENCE_LINE = /^([ \t]*)(`{3,}|~{3,})[ \t]*(.*)$/;

// A diagram that already configures itself, by directive or by YAML front matter, is left alone.
const CONFIGURES_ITSELF = /^(%%\{|---[ \t]*$)/;

// Mermaid honours a per-diagram directive even when it has not been configured globally, which is
// what makes this work: the browser build of the renderer never calls mermaid.initialize, so the
// mermaidConfig passed to the rehype plugin is silently discarded and the diagram source is the
// only channel left for a theme.
const themeDirective = (theme: ResolvedTheme) =>
  `%%{init: {"theme":"${theme === "dark" ? "dark" : "default"}"}}%%`;

function firstMeaningfulLine(lines: string[], start: number): string {
  for (let i = start; i < lines.length; i += 1) {
    const trimmed = (lines[i] ?? "").trim();
    if (trimmed !== "") return trimmed;
  }
  return "";
}

/**
 * Applies a theme to every mermaid block in a markdown document by prefixing each diagram with an
 * init directive, returning the document unchanged when there is nothing to theme.
 *
 * Walks the document line by line, tracking which fence is open, because a mermaid fence quoted
 * inside a longer outer fence is a literal example, not a diagram — a flat pattern match would
 * inject the directive into it. Per CommonMark, a fence closes only on a marker of the same
 * character at least as long as the opener, with nothing after it.
 *
 * Rewrites only the copy handed to the renderer — the stored document keeps whatever the author
 * wrote, so a theme change never edits a user's content.
 */
export function withMermaidTheme(markdown: string, theme: ResolvedTheme): string {
  if (!markdown.includes("mermaid")) {
    return markdown;
  }

  const lines = markdown.split("\n");
  const out: string[] = [];
  let openFence: { char: string; length: number } | null = null;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index] ?? "";
    out.push(line);

    const fence = line.match(FENCE_LINE);
    if (!fence) continue;
    const indent = fence[1] ?? "";
    const marker = fence[2] ?? "";
    const rawInfo = fence[3] ?? "";
    const char = marker.charAt(0);
    const info = rawInfo.trim();

    if (openFence) {
      if (char === openFence.char && marker.length >= openFence.length && info === "") {
        openFence = null;
      }
      continue;
    }

    // An info string containing a backtick cannot open a backtick fence (CommonMark).
    if (char === "`" && rawInfo.includes("`")) continue;

    openFence = { char, length: marker.length };

    if (/^mermaid\b/.test(info) && !CONFIGURES_ITSELF.test(firstMeaningfulLine(lines, index + 1))) {
      out.push(`${indent}${themeDirective(theme)}`);
    }
  }

  return out.join("\n");
}
