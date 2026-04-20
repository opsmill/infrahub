import { useAtomValue } from "jotai";
import { type FormEvent, useState } from "react";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { ObjectPicker } from "./object-picker";
import { HIDDEN_NAMESPACES } from "./utils";

type SearchParams = {
  sourceId: string;
  destinationId: string;
  maxDepth: number;
  maxPaths: number;
  kindFilter: string[];
  excludedKinds: string[];
};

type ObjectSelectorProps = {
  onSearch: (params: SearchParams) => void;
  isLoading: boolean;
  initialSourceId?: string;
  initialDestinationId?: string;
  maxDepth?: number;
  maxPaths?: number;
  excludedKinds?: string[];
  onMaxDepthChange?: (value: number) => void;
  onMaxPathsChange?: (value: number) => void;
  onExcludedKindsChange?: (kinds: string[]) => void;
};

export function ObjectSelector({
  onSearch,
  isLoading,
  initialSourceId = "",
  initialDestinationId = "",
  maxDepth = 5,
  maxPaths = 10,
  excludedKinds = [],
  onMaxDepthChange,
  onMaxPathsChange,
  onExcludedKindsChange,
}: ObjectSelectorProps) {
  const [sourceId, setSourceId] = useState(initialSourceId);
  const [sourceLabel, setSourceLabel] = useState("");
  const [destinationId, setDestinationId] = useState(initialDestinationId);
  const [destinationLabel, setDestinationLabel] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [selectedKinds, setSelectedKinds] = useState<string[]>([]);
  const [kindSearch, setKindSearch] = useState("");
  const [excludeSearch, setExcludeSearch] = useState("");

  const allNodeSchemas = useAtomValue(nodeSchemasAtom);
  // Hide kinds from system namespaces that are always excluded by the backend
  const nodeSchemas = allNodeSchemas.filter((s) => !HIDDEN_NAMESPACES.has(s.namespace as string));

  const filteredKinds = kindSearch
    ? nodeSchemas.filter(
        (s) =>
          (s.label ?? "").toLowerCase().includes(kindSearch.toLowerCase()) ||
          (s.kind ?? "").toLowerCase().includes(kindSearch.toLowerCase())
      )
    : nodeSchemas;

  const filteredExcludeKinds = excludeSearch
    ? nodeSchemas.filter(
        (s) =>
          (s.label ?? "").toLowerCase().includes(excludeSearch.toLowerCase()) ||
          (s.kind ?? "").toLowerCase().includes(excludeSearch.toLowerCase())
      )
    : nodeSchemas;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (sourceId && destinationId) {
      onSearch({
        sourceId,
        destinationId,
        maxDepth,
        maxPaths,
        kindFilter: selectedKinds,
        excludedKinds,
      });
    }
  }

  function handleSwap() {
    const prevSourceId = sourceId;
    const prevSourceLabel = sourceLabel;
    setSourceId(destinationId);
    setSourceLabel(destinationLabel);
    setDestinationId(prevSourceId);
    setDestinationLabel(prevSourceLabel);
  }

  function toggleKind(kind: string) {
    setSelectedKinds((prev) =>
      prev.includes(kind) ? prev.filter((k) => k !== kind) : [...prev, kind]
    );
  }

  function toggleExcludedKind(kind: string) {
    const updated = excludedKinds.includes(kind)
      ? excludedKinds.filter((k) => k !== kind)
      : [...excludedKinds, kind];
    onExcludedKindsChange?.(updated);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4">
      <ObjectPicker
        label="Source Object"
        value={sourceId}
        displayLabel={sourceLabel}
        onChange={(id, label) => {
          setSourceId(id);
          setSourceLabel(label);
        }}
      />

      {(sourceId || destinationId) && (
        <button
          type="button"
          onClick={handleSwap}
          className="flex w-full items-center justify-center gap-1 rounded border border-gray-200 px-3 py-1 text-gray-500 text-xs hover:bg-gray-50"
        >
          ⇅ Swap
        </button>
      )}

      <ObjectPicker
        label="Destination Object"
        value={destinationId}
        displayLabel={destinationLabel}
        onChange={(id, label) => {
          setDestinationId(id);
          setDestinationLabel(label);
        }}
      />

      {/* Excluded kinds chips */}
      {excludedKinds.length > 0 && (
        <div className="space-y-1">
          <span className="block font-medium text-gray-600 text-xs">
            Excluded from paths ({excludedKinds.length})
          </span>
          <div className="flex flex-wrap gap-1">
            {excludedKinds.map((kind) => (
              <span
                key={kind}
                className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[10px] text-red-700"
              >
                {kind}
                <button
                  type="button"
                  onClick={() => toggleExcludedKind(kind)}
                  className="text-red-400 hover:text-red-600"
                >
                  ✕
                </button>
              </span>
            ))}
            <button
              type="button"
              onClick={() => onExcludedKindsChange?.([])}
              className="text-[10px] text-red-500 hover:text-red-700"
            >
              Clear all
            </button>
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="text-blue-600 text-sm hover:text-blue-800"
      >
        {showAdvanced ? "Hide" : "Show"} Advanced Options
      </button>

      {showAdvanced && (
        <div className="space-y-3 rounded-md border border-gray-200 p-3">
          <div className="flex gap-4">
            <div className="flex-1">
              <label htmlFor="max-depth" className="block font-medium text-gray-600 text-xs">
                Max Depth
              </label>
              <input
                id="max-depth"
                type="number"
                min={1}
                max={20}
                value={maxDepth}
                onChange={(e) => onMaxDepthChange?.(Number(e.target.value))}
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
            <div className="flex-1">
              <label htmlFor="max-paths" className="block font-medium text-gray-600 text-xs">
                Max Paths
              </label>
              <input
                id="max-paths"
                type="number"
                min={1}
                max={100}
                value={maxPaths}
                onChange={(e) => onMaxPathsChange?.(Number(e.target.value))}
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
          </div>

          <div>
            <span className="mb-1 block font-medium text-gray-600 text-xs">
              Include only these kinds {selectedKinds.length > 0 && `(${selectedKinds.length})`}
            </span>
            <input
              type="text"
              value={kindSearch}
              onChange={(e) => setKindSearch(e.target.value)}
              placeholder="Search kinds..."
              className="mb-1 w-full rounded border border-gray-200 px-2 py-1 text-xs focus:border-blue-400 focus:outline-none"
            />
            <div className="max-h-32 overflow-y-auto rounded border border-gray-200">
              {filteredKinds.map((schema) => (
                <label
                  key={schema.kind}
                  className="flex cursor-pointer items-center gap-2 px-2 py-1 text-xs hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    checked={selectedKinds.includes(schema.kind as string)}
                    onChange={() => toggleKind(schema.kind as string)}
                    className="rounded border-gray-300"
                  />
                  <span className="truncate">{schema.label ?? schema.kind}</span>
                  <span className="ml-auto text-gray-400">{schema.namespace}</span>
                </label>
              ))}
            </div>
            {selectedKinds.length > 0 && (
              <button
                type="button"
                onClick={() => setSelectedKinds([])}
                className="mt-1 text-blue-600 text-xs hover:text-blue-800"
              >
                Clear
              </button>
            )}
          </div>

          <div>
            <span className="mb-1 block font-medium text-gray-600 text-xs">
              Exclude kinds {excludedKinds.length > 0 && `(${excludedKinds.length})`}
            </span>
            <input
              type="text"
              value={excludeSearch}
              onChange={(e) => setExcludeSearch(e.target.value)}
              placeholder="Search kinds to exclude..."
              className="mb-1 w-full rounded border border-gray-200 px-2 py-1 text-xs focus:border-blue-400 focus:outline-none"
            />
            <div className="max-h-32 overflow-y-auto rounded border border-gray-200">
              {filteredExcludeKinds.map((schema) => (
                <label
                  key={schema.kind}
                  className="flex cursor-pointer items-center gap-2 px-2 py-1 text-xs hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    checked={excludedKinds.includes(schema.kind as string)}
                    onChange={() => toggleExcludedKind(schema.kind as string)}
                    className="rounded border-gray-300"
                  />
                  <span className="truncate">{schema.label ?? schema.kind}</span>
                  <span className="ml-auto text-gray-400">{schema.namespace}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      )}

      <button
        type="submit"
        disabled={isLoading || !sourceId || !destinationId}
        className="w-full rounded-md bg-blue-600 px-4 py-2 font-medium text-sm text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
      >
        {isLoading ? "Finding Paths..." : "Find Paths"}
      </button>
    </form>
  );
}
