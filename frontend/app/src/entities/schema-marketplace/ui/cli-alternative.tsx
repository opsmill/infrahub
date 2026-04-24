import { useQuery } from "@tanstack/react-query";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { Button } from "@/shared/components/ui/button";
import { classNames } from "@/shared/utils/common";

import { fetchCliSnippet } from "@/entities/schema-marketplace/api/marketplace.queries";
import type { MarketplaceInstallItem } from "@/entities/schema-marketplace/types";

interface CliAlternativeProps {
  selection: MarketplaceInstallItem[];
  branchName?: string;
  className?: string;
}

function itemToToken(item: MarketplaceInstallItem): string {
  const suffix = item.semver ? `@${item.semver}` : "";
  return `${item.kind}:${item.namespace}/${item.name}${suffix}`;
}

function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable — no-op */
    }
  };
  return (
    <Button
      type="button"
      variant="ghost"
      size="xs"
      onClick={copy}
      aria-label={copied ? "Copied" : label}
      className="shrink-0"
    >
      <Icon icon={copied ? "mdi:check" : "mdi:content-copy"} />
      <span className="ml-1">{copied ? "Copied" : label}</span>
    </Button>
  );
}

export function CliAlternative({ selection, branchName = "main", className }: CliAlternativeProps) {
  const tokens = selection.map(itemToToken);
  const query = useQuery({
    queryKey: ["schema-marketplace", "cli-snippet", tokens.join("|"), branchName],
    queryFn: () => fetchCliSnippet({ items: tokens, branchName }),
    enabled: tokens.length > 0,
  });

  // Rendered stand-alone — callers wrap in <Card> if they want a surface. The
  // parent marketplace page already does that; keeping a card here would
  // double up in the sidebar.
  return (
    <div className={classNames("flex flex-col gap-2", className)}>
      {tokens.length === 0 && (
        <p className="text-gray-500 text-xs">
          Pick one or more schemas or collections above to generate commands.
        </p>
      )}

      {query.isPending && tokens.length > 0 && (
        <p className="text-gray-500 text-xs">Generating commands…</p>
      )}

      {query.isError && (
        <div className="rounded-md bg-red-50 p-2 text-red-700 text-xs">
          <p className="mb-0.5 font-semibold">Unable to generate commands</p>
          <p>{(query.error as Error).message}</p>
        </div>
      )}

      {query.data && (
        <>
          <div className="flex items-center justify-between gap-2">
            <span className="text-gray-500 text-xs">
              {query.data.downloads.length} item{query.data.downloads.length === 1 ? "" : "s"} · run
              in your shell
            </span>
            <CopyButton value={query.data.rendered} label="Copy all" />
          </div>
          <pre className="max-h-48 overflow-auto rounded-md bg-gray-900 p-3 text-green-200 text-xs leading-5">
            <code>{query.data.rendered}</code>
          </pre>
          <details className="group text-xs">
            <summary className="flex cursor-pointer list-none items-center gap-1 text-gray-500 hover:text-gray-700">
              <Icon
                icon="mdi:chevron-right"
                className="transition-transform group-open:rotate-90"
              />
              Copy individual lines
            </summary>
            <ul className="flex flex-col gap-1 pt-1.5">
              {query.data.downloads.map((download) => (
                <li
                  key={`${download.namespace}/${download.name}-${download.semver ?? "latest"}`}
                  className="flex items-center justify-between gap-2 pl-4 font-mono"
                >
                  <span className="truncate">{download.command}</span>
                  <CopyButton value={download.command} />
                </li>
              ))}
              <li className="flex items-center justify-between gap-2 pl-4 font-mono">
                <span className="truncate">{query.data.load_command}</span>
                <CopyButton value={query.data.load_command} />
              </li>
            </ul>
          </details>
        </>
      )}
    </div>
  );
}
