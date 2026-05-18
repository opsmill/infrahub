import { Command } from "cmdk";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { copyAllPathsAsText, formatPathAsText } from "../format-paths";
import { useGetPathTraversal } from "../queries/get-path-traversal.query";
import { getKindColor } from "../utils";
import { PathModeForm } from "./path-mode-form";
import {
  formValuesToParams,
  type PathModeFormValues,
  paramsToFormValues,
  usePathModeParams,
} from "./use-path-mode-params";

export function PathModeSidebar() {
  const [params, setParams] = usePathModeParams();
  const formValues = paramsToFormValues(params);
  const [copyFeedback, setCopyFeedback] = useState("");

  const form = useForm<PathModeFormValues>({
    defaultValues: formValues,
    values: formValues,
  });

  const query = useGetPathTraversal(
    {
      sourceId: params.source,
      destinationId: params.destination,
      maxDepth: params.depth,
      maxPaths: params.maxPaths,
      kindFilter: params.kindFilter,
      excludedKinds: params.excludedKinds,
    },
    { enabled: !!params.source && !!params.destination }
  );

  async function handleCopy(text: string) {
    await navigator.clipboard.writeText(text);
    setCopyFeedback("Copied!");
    setTimeout(() => setCopyFeedback(""), 2000);
  }

  const data = query.data;
  const selectedPath = params.selectedPath;

  return (
    <div className="flex h-full flex-col">
      <PathModeForm
        form={form}
        onSubmit={(values) => setParams(formValuesToParams(values))}
        isPending={query.isPending && query.fetchStatus === "fetching"}
      />

      {data && (
        <div className="border-gray-200 border-t p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-medium text-gray-700 text-sm">
              {data.count} path{data.count !== 1 ? "s" : ""} found
            </h3>
            {data.paths.length > 0 && (
              <button
                type="button"
                onClick={() => handleCopy(copyAllPathsAsText(data))}
                className="rounded px-2 py-0.5 text-blue-600 text-xs hover:bg-blue-50"
                title="Copy all paths to clipboard"
              >
                {copyFeedback || "Copy all"}
              </button>
            )}
          </div>

          {data.paths.length > 0 ? (
            <Command
              shouldFilter={false}
              loop
              disablePointerSelection
              value={String(selectedPath)}
              onValueChange={(value) => setParams({ selectedPath: Number(value) })}
              label="Path results"
            >
              <Command.List className="space-y-1">
                {data.paths.map((path, index) => {
                  const isExpanded = selectedPath === index;
                  return (
                    <Command.Item
                      key={index}
                      value={String(index)}
                      onSelect={() => setParams({ selectedPath: index })}
                      className="group block cursor-pointer rounded-md border border-transparent transition-colors hover:border-gray-200 hover:bg-gray-50 data-[selected=true]:border-blue-300 data-[selected=true]:bg-blue-50"
                    >
                      <div className="flex items-center gap-1 p-2">
                        <div className="flex min-w-0 flex-1 items-center gap-2">
                          <span
                            className={`font-medium text-xs ${
                              isExpanded ? "text-blue-700" : "text-gray-600"
                            }`}
                          >
                            Path {index + 1}
                          </span>
                          <span className="rounded-full bg-gray-200 px-1.5 py-0.5 text-[10px] text-gray-500">
                            {path.depth} hop{path.depth !== 1 ? "s" : ""}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCopy(formatPathAsText(data, index));
                          }}
                          className="shrink-0 rounded p-0.5 text-gray-300 opacity-0 transition-opacity hover:text-gray-500 focus-visible:opacity-100 group-hover:opacity-100"
                          title="Copy this path"
                        >
                          copy
                        </button>
                      </div>
                      {isExpanded && (
                        <ul className="space-y-1 px-3 pb-2">
                          {path.hops.map((hop, hopIndex) => (
                            <li
                              key={`${hop.node.id}-${hopIndex}`}
                              className="flex items-center gap-2 text-[11px] text-gray-700"
                            >
                              <span
                                className="size-1.5 shrink-0 rounded-full"
                                style={{ backgroundColor: getKindColor(hop.node.kind) }}
                              />
                              <span className="truncate">{hop.node.display_label}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </Command.Item>
                  );
                })}
              </Command.List>
            </Command>
          ) : (
            <div className="text-center text-gray-400 text-sm">No paths found</div>
          )}
        </div>
      )}
    </div>
  );
}
