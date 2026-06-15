import { Button, Tooltip } from "@infrahub/ui";
import { Command } from "cmdk";

import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";
import { classNames } from "@/shared/utils/common";

import type { PathResult } from "../domain/path-traversal.types";
import { getKindColor } from "./utils";

type Variant = "blue" | "amber";

const VARIANT_CLASSES: Record<
  Variant,
  {
    headerBanner: string;
    headerText: string;
    selected: string;
    selectedTitle: string;
  }
> = {
  blue: {
    headerBanner: "",
    headerText: "text-gray-700",
    selected: "data-[selected=true]:border-blue-300 data-[selected=true]:bg-blue-50",
    selectedTitle: "text-blue-700",
  },
  amber: {
    headerBanner: "mb-2 rounded-md border border-amber-200 bg-amber-50 p-2",
    headerText: "font-medium text-amber-800 text-xs",
    selected: "data-[selected=true]:border-amber-300 data-[selected=true]:bg-amber-50",
    selectedTitle: "text-amber-700",
  },
};

type PathResultsListProps = {
  paths: PathResult[];
  countLabel: string;
  selectedIndex: number;
  onSelect: (index: number) => void;
  variant: Variant;
  getItemTitle: (path: PathResult, index: number) => string;
  getItemSubtitle?: (path: PathResult, index: number) => string | undefined;
  emptyMessage?: string;
  copyAllText?: () => string;
  copyItemText?: (index: number) => string;
  ariaLabel?: string;
};

export function PathResultsList({
  paths,
  countLabel,
  selectedIndex,
  onSelect,
  variant,
  getItemTitle,
  getItemSubtitle,
  emptyMessage = "No results found",
  copyAllText,
  copyItemText,
  ariaLabel = "Path results",
}: PathResultsListProps) {
  const v = VARIANT_CLASSES[variant];
  const { isCopied, copyToClipboard } = useCopyToClipboard();

  return (
    <div className="border-gray-200 border-t p-4">
      <div className={classNames("mb-3 flex items-center justify-between", v.headerBanner)}>
        <h3 className={classNames("font-medium text-sm", v.headerText)}>{countLabel}</h3>
        {paths.length > 0 && copyAllText && (
          <Tooltip message="Copy all to clipboard">
            <Button
              variant="ghost"
              size="xs"
              onPress={() => copyToClipboard(copyAllText())}
              className="px-2 py-0.5 text-blue-600 text-xs data-hovered:bg-blue-50"
            >
              {isCopied ? "Copied!" : "Copy all"}
            </Button>
          </Tooltip>
        )}
      </div>

      {paths.length > 0 ? (
        <Command
          shouldFilter={false}
          loop
          disablePointerSelection
          value={String(selectedIndex)}
          onValueChange={(value) => onSelect(Number(value))}
          label={ariaLabel}
        >
          <Command.List className="space-y-1">
            {paths.map((path, index) => {
              const isExpanded = selectedIndex === index;
              const subtitle = getItemSubtitle?.(path, index);
              return (
                <Command.Item
                  key={index}
                  value={String(index)}
                  onSelect={() => onSelect(index)}
                  className={classNames(
                    "group block cursor-pointer rounded-md border border-transparent transition-colors hover:border-gray-200 hover:bg-gray-50",
                    v.selected
                  )}
                >
                  <div className="flex items-center gap-1 p-2">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                      <span
                        className={classNames(
                          "truncate font-medium text-xs",
                          isExpanded ? v.selectedTitle : "text-gray-600"
                        )}
                      >
                        {getItemTitle(path, index)}
                      </span>
                      <span className="shrink-0 rounded-full bg-gray-200 px-1.5 py-0.5 text-[10px] text-gray-500">
                        {path.depth} hop{path.depth !== 1 ? "s" : ""}
                      </span>
                    </div>
                    {copyItemText && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          copyToClipboard(copyItemText(index));
                        }}
                        className="shrink-0 rounded p-0.5 text-gray-300 opacity-0 transition-opacity hover:text-gray-500 focus-visible:opacity-100 group-hover:opacity-100"
                        title="Copy this entry"
                      >
                        copy
                      </button>
                    )}
                  </div>
                  {subtitle && !isExpanded && (
                    <div className="truncate px-3 pb-2 text-[10px] text-gray-400">{subtitle}</div>
                  )}
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
        <div className="text-center text-gray-400 text-sm">{emptyMessage}</div>
      )}
    </div>
  );
}
