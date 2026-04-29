import { type FormEvent, useState } from "react";

import { KindMultiSelect } from "@/shared/components/inputs/kind-multi-select";

import { ObjectPicker } from "./object-picker";

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

          <KindMultiSelect
            value={selectedKinds}
            onChange={setSelectedKinds}
            label="Include only these kinds"
          />

          <KindMultiSelect
            value={excludedKinds}
            onChange={(kinds) => onExcludedKindsChange?.(kinds)}
            label="Exclude kinds"
            placeholder="Search kinds to exclude..."
            showChips
            chipTone="red"
          />
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
