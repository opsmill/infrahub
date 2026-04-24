import { useQuery } from "@tanstack/react-query";
import { Icon } from "@iconify-icon/react";
import { useEffect, useState } from "react";
import { Heading } from "react-aria-components";

import { Modal } from "@/shared/components/aria/modal";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import { MarkdownRender } from "@/shared/components/editor/markdown/markdown-render";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";

import {
  fetchMarketplaceSchema,
  fetchMarketplaceSchemaVersionPreview,
} from "@/entities/schema-marketplace/api/marketplace.queries";
import type {
  MarketplaceInstallItem,
  MarketplaceSchemaSummary,
} from "@/entities/schema-marketplace/types";

interface SchemaDetailModalProps {
  schema: MarketplaceSchemaSummary | null;
  currentSelection: MarketplaceInstallItem[];
  onApply: (item: MarketplaceInstallItem) => void;
  onRemove: (item: MarketplaceInstallItem) => void;
  onClose: () => void;
}

function schemaKey(namespace: string, name: string): string {
  return `schema:${namespace}/${name}`;
}

export function SchemaDetailModal({
  schema,
  currentSelection,
  onApply,
  onRemove,
  onClose,
}: SchemaDetailModalProps) {
  // Keep the Modal mounted across open/close so react-aria can drive the exit
  // animation. `schema === null` is the closed state; we early-return from the
  // render body when that's the case.
  const isOpen = schema !== null;

  const detail = useQuery({
    queryKey: ["schema-marketplace", "schema", schema?.namespace, schema?.name],
    queryFn: () => fetchMarketplaceSchema(schema!.namespace, schema!.name),
    enabled: isOpen,
  });

  const versions = detail.data?.versions ?? [];
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);

  // Seed the version picker once detail loads. Reset when opening a different
  // schema so the stale id from a previous card doesn't leak across.
  useEffect(() => {
    if (!detail.data) {
      setSelectedVersionId(null);
      return;
    }
    setSelectedVersionId(
      detail.data.latest_version?.id ?? detail.data.versions[0]?.id ?? null
    );
  }, [detail.data]);

  const selectedVersion = versions.find((v) => v.id === selectedVersionId) ?? null;

  const yaml = useQuery({
    queryKey: [
      "schema-marketplace",
      "schema-version-preview",
      schema?.namespace,
      schema?.name,
      selectedVersion?.semver,
    ],
    queryFn: () =>
      fetchMarketplaceSchemaVersionPreview(
        schema!.namespace,
        schema!.name,
        selectedVersion!.semver
      ),
    enabled: isOpen && !!selectedVersion && !!schema,
    staleTime: 5 * 60 * 1000,
  });

  const existing =
    schema &&
    (currentSelection.find(
      (s) => `${s.kind}:${s.namespace}/${s.name}` === schemaKey(schema.namespace, schema.name)
    ) ?? null);

  const chosenSemver = selectedVersion?.semver ?? null;
  const sameAsExisting = !!existing && existing.semver === chosenSemver;

  return (
    <Modal
      isOpen={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      className="w-full max-w-3xl"
      aria-label={schema ? `${schema.display_name || schema.name} details` : "Schema details"}
    >
      {({ close }) => {
        if (!schema) return null;
        const title = schema.display_name || schema.name;

        const apply = () => {
          if (!chosenSemver) return;
          onApply({
            kind: "schema",
            namespace: schema.namespace,
            name: schema.name,
            semver: chosenSemver,
          });
          close();
        };

        const remove = () => {
          if (!existing) return;
          onRemove(existing);
          close();
        };

        return (
          <div className="flex h-full min-h-0 flex-col gap-3 p-4">
            <header className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <Heading slot="title" className="flex items-center gap-2 font-semibold text-lg">
                  <Icon icon="mdi:file-code" />
                  <span className="truncate">{title}</span>
                </Heading>
                <p className="font-mono text-gray-500 text-xs">
                  {schema.namespace}/{schema.name}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Close"
                onClick={() => close()}
              >
                <Icon icon="mdi:close" />
              </Button>
            </header>

            {schema.description && (
              <p className="text-gray-600 text-sm">{schema.description}</p>
            )}

            {schema.tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {schema.tags.map((t) => (
                  <Badge key={t.id ?? t.name} variant="lightgray-outline">
                    {t.name}
                  </Badge>
                ))}
              </div>
            )}

            {detail.isPending && <LoadingIndicator />}
            {detail.error && (
              <div className="rounded-md bg-red-50 p-3 text-red-700 text-sm">
                Failed to load schema detail: {(detail.error as Error).message}
              </div>
            )}

            {versions.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <label htmlFor="schema-version-select" className="text-sm">
                  Version
                </label>
                <select
                  id="schema-version-select"
                  className="rounded-md border border-gray-200 p-1.5 text-sm"
                  value={selectedVersionId ?? ""}
                  onChange={(event) => setSelectedVersionId(event.target.value)}
                >
                  {versions.map((v) => (
                    <option key={v.id} value={v.id}>
                      v{v.semver}
                      {v.status !== "published" ? ` (${v.status})` : ""}
                    </option>
                  ))}
                </select>
                {existing && (
                  <Badge variant="gray-outline">
                    Selected: v{existing.semver ?? "latest"}
                  </Badge>
                )}
                {selectedVersion?.changelog && (
                  <span className="truncate text-gray-500 text-xs">
                    {selectedVersion.changelog}
                  </span>
                )}
              </div>
            )}

            <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto">
              {detail.data?.readme && (
                <section>
                  <h3 className="mb-1 font-semibold text-sm">Readme</h3>
                  <div className="rounded-md border border-gray-200 p-3">
                    <MarkdownRender markdownText={detail.data.readme} />
                  </div>
                </section>
              )}

              <section className="flex min-h-0 flex-col">
                <h3 className="mb-1 font-semibold text-sm">
                  YAML preview{selectedVersion ? ` — v${selectedVersion.semver}` : ""}
                </h3>
                {yaml.isPending && selectedVersion && <LoadingIndicator />}
                {yaml.error && (
                  // Marketplace fetches routinely 502 when the upstream is
                  // slow or being redeployed -- don't surface that raw; frame
                  // it as "preview unavailable, install still works".
                  <div className="rounded-md bg-yellow-50 p-3 text-yellow-800 text-sm">
                    <p className="mb-1 font-semibold">Preview unavailable</p>
                    <p>
                      The Marketplace didn't return version content (
                      <span className="font-mono">
                        {(yaml.error as Error).message}
                      </span>
                      ). Install still works -- try again in a moment.
                    </p>
                  </div>
                )}
                {yaml.data && (
                  <CodeViewer language="yaml" className="max-h-96">
                    {yaml.data.content}
                  </CodeViewer>
                )}
              </section>
            </div>

            <footer className="flex flex-wrap items-center justify-end gap-2 border-gray-200 border-t pt-3">
              {existing && (
                <Button variant="outline" onClick={remove}>
                  <Icon icon="mdi:close" className="mr-1" /> Remove from selection
                </Button>
              )}
              <Button
                variant="primary"
                disabled={!chosenSemver || sameAsExisting}
                onClick={apply}
              >
                {existing
                  ? sameAsExisting
                    ? `v${chosenSemver} already added`
                    : `Use v${chosenSemver} instead`
                  : `Add to install${chosenSemver ? ` @ v${chosenSemver}` : ""}`}
              </Button>
            </footer>
          </div>
        );
      }}
    </Modal>
  );
}
