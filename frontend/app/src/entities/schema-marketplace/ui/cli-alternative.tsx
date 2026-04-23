import { useQuery } from "@tanstack/react-query";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
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
      variant="outline"
      size="xs"
      onClick={copy}
      aria-label={copied ? "Copied" : label}
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

  return (
    <Card className={classNames("flex flex-col gap-3", className)}>
      <header className="flex items-center gap-2 font-semibold">
        <Icon icon="mdi:console" />
        <span>Install via infrahubctl</span>
      </header>

      <div className="rounded-md bg-blue-50 p-3 text-custom-blue-700 text-sm">
        <p className="mb-1 font-semibold">No Git commit required</p>
        <p>
          The <code className="font-mono">infrahubctl</code> path runs against your Infrahub
          instance using your existing <code className="font-mono">INFRAHUB_ADDRESS</code> and{" "}
          <code className="font-mono">INFRAHUB_API_TOKEN</code>. Schemas are applied directly via
          the API — they are <em>not</em> committed to any Git repository, which is why this flow
          works when you have no writable repository configured.
        </p>
      </div>

      {tokens.length === 0 && (
        <p className="text-gray-500 text-sm">
          Pick one or more schemas or collections above to generate commands.
        </p>
      )}

      {query.isPending && tokens.length > 0 && (
        <p className="text-gray-500 text-sm">Generating commands…</p>
      )}

      {query.isError && (
        <div className="rounded-md bg-red-50 p-3 text-red-700 text-sm">
          <p className="mb-1 font-semibold">Unable to generate commands</p>
          <p>{(query.error as Error).message}</p>
        </div>
      )}

      {query.data && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-gray-500 text-xs">
              {query.data.downloads.length} item{query.data.downloads.length === 1 ? "" : "s"}
            </span>
            <CopyButton value={query.data.rendered} label="Copy all" />
          </div>
          <pre className="overflow-x-auto rounded-md bg-gray-900 p-3 text-green-200 text-xs leading-5">
            <code>{query.data.rendered}</code>
          </pre>
          <ul className="flex flex-col gap-1">
            {query.data.downloads.map((download) => (
              <li
                key={`${download.namespace}/${download.name}-${download.semver ?? "latest"}`}
                className="flex items-center justify-between gap-2 font-mono text-xs"
              >
                <span className="truncate">{download.command}</span>
                <CopyButton value={download.command} label="Copy" />
              </li>
            ))}
            <li className="flex items-center justify-between gap-2 font-mono text-xs">
              <span className="truncate">{query.data.load_command}</span>
              <CopyButton value={query.data.load_command} label="Copy" />
            </li>
          </ul>
        </div>
      )}
    </Card>
  );
}
