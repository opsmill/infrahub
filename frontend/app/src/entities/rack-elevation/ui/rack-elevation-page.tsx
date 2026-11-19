import {
  Button,
  LinkButton,
  Select,
  SelectItem,
  SelectList,
  SelectTrigger,
  Sheet,
} from "@infrahub/ui";
import { Box, DownloadIcon, PencilIcon, PlusIcon, Rows3Icon } from "lucide-react";
import React from "react";
import { useSearchParams } from "react-router";

import { classNames } from "@/shared/utils/common";

import type { ElevationItem, RackFace } from "@/entities/rack-elevation/domain/model/elevation";
import {
  applyLabelChoices,
  getLabelOptions,
} from "@/entities/rack-elevation/domain/rules/apply-labels";
import { buildElevation } from "@/entities/rack-elevation/domain/rules/build-elevation";
import {
  buildPlacementUpdates,
  type Placement,
} from "@/entities/rack-elevation/domain/rules/placement";
import { getDisplayLabel } from "@/entities/rack-elevation/domain/rules/resolve-path";
import { ChangesPanel } from "@/entities/rack-elevation/ui/changes-panel";
import { ExportDialog } from "@/entities/rack-elevation/ui/export-dialog";
import { FilterBar } from "@/entities/rack-elevation/ui/filter-bar";
import { LabelsMenu } from "@/entities/rack-elevation/ui/labels-menu";
import { ObjectDetails, Section } from "@/entities/rack-elevation/ui/object-details";
import { RackElevation2D } from "@/entities/rack-elevation/ui/rack-elevation-2d";
import { RackElevation3D } from "@/entities/rack-elevation/ui/rack-elevation-3d";
import { useRackElevationStore } from "@/entities/rack-elevation/ui/rack-elevation-store";
import { UnitDetails } from "@/entities/rack-elevation/ui/unit-details";
import { useElevationFilter } from "@/entities/rack-elevation/ui/use-elevation-filter";
import { useLabelChoices } from "@/entities/rack-elevation/ui/use-label-choices";

type SheetContent =
  | { type: "node"; stack: string[] }
  | { type: "unit"; unit: number; face: RackFace };

type ViewMode = "2d" | "3d";

export function RackElevationPage() {
  const { mappings, nodes, schema, updateAttributes } = useRackElevationStore();
  const [searchParams, setSearchParams] = useSearchParams();
  const [sheet, setSheet] = React.useState<SheetContent | null>(null);
  const [isSheetOpen, setIsSheetOpen] = React.useState(false);

  const mapping =
    mappings.find((candidate) => candidate.id === searchParams.get("mapping")) ?? mappings[0];
  const racks = mapping
    ? Object.values(nodes).filter((node) => node.kind === mapping.rackKind)
    : [];
  const rack = racks.find((node) => node.id === searchParams.get("rack")) ?? racks[0];
  const view: ViewMode = searchParams.get("view") === "3d" ? "3d" : "2d";
  const mappedElevation = mapping && rack ? buildElevation(mapping, rack, nodes, schema) : null;
  const { choices: labelChoices, setChoices: setLabelChoices } = useLabelChoices();
  const [isExportOpen, setIsExportOpen] = React.useState(false);
  const elevation = mappedElevation
    ? applyLabelChoices(mappedElevation, labelChoices, nodes, schema)
    : null;
  const labelOptions = mappedElevation ? getLabelOptions(mappedElevation, nodes, schema) : null;
  const { filter, setFilter, facets, matchedKeys, matchCount, totalCount } =
    useElevationFilter(elevation);

  const setParam = (key: string, value: string | null) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (value === null) next.delete(key);
      else next.set(key, value);
      if (key === "mapping") next.delete("rack");
      return next;
    });
  };

  const openSheet = (content: SheetContent) => {
    setSheet(content);
    setIsSheetOpen(true);
  };
  const openNode = (nodeId: string) => {
    const stack = sheet?.type === "node" && isSheetOpen ? sheet.stack : [];
    openSheet({ type: "node", stack: [...stack, nodeId] });
  };
  const openRootNode = (nodeId: string) => openSheet({ type: "node", stack: [nodeId] });
  const selectedKey =
    isSheetOpen && sheet?.type === "node"
      ? elevation?.placed.find((item) => item.node.id === sheet.stack.at(-1))?.key
      : null;

  const interactions = {
    selectedKey,
    matchedKeys,
    onSelectItem: (item: ElevationItem) => openRootNode(item.node.id),
    onSelectRack: () => rack && openRootNode(rack.id),
    onSelectUnit: (unit: number, face: RackFace) => openSheet({ type: "unit", unit, face }),
    onMoveItem: mapping
      ? (item: ElevationItem, placement: Placement) =>
          updateAttributes(buildPlacementUpdates(item, placement, mapping, schema))
      : undefined,
  };

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b p-4">
        <div className="mr-4">
          <h1 className="font-semibold text-lg">Rack elevation</h1>
          <p className="text-foreground-muted text-xs">Prototype with sample data</p>
        </div>
        <Select
          aria-label="Mapping"
          className="w-56"
          selectedKey={mapping?.id ?? null}
          onSelectionChange={(key) => setParam("mapping", String(key))}
        >
          <SelectTrigger size="sm" />
          <SelectList items={mappings}>
            {(item) => <SelectItem id={item.id}>{item.name}</SelectItem>}
          </SelectList>
        </Select>
        <Select
          aria-label="Rack"
          className="w-56"
          selectedKey={rack?.id ?? null}
          onSelectionChange={(key) => setParam("rack", String(key))}
        >
          <SelectTrigger size="sm" />
          <SelectList items={racks}>
            {(item) => <SelectItem id={item.id}>{getDisplayLabel(item, schema)}</SelectItem>}
          </SelectList>
        </Select>
        <div className="flex rounded-lg border bg-content-muted p-0.5">
          {(["2d", "3d"] as const).map((mode) => (
            <Button
              key={mode}
              size="xs"
              variant={view === mode ? "outline" : "ghost"}
              onPress={() => setParam("view", mode === "2d" ? null : mode)}
            >
              {mode === "2d" ? <Rows3Icon /> : <Box />}
              {mode === "2d" ? "Front and rear" : "3D"}
            </Button>
          ))}
        </div>
        <div className="ml-auto flex gap-2">
          {mapping && (
            <LinkButton size="sm" variant="outline" href={`/rack-elevation/${mapping.id}/edit`}>
              <PencilIcon />
              Edit mapping
            </LinkButton>
          )}
          <LinkButton size="sm" variant="primary" href="/rack-elevation/new">
            <PlusIcon />
            New mapping
          </LinkButton>
        </div>
      </header>
      {elevation && (
        <FilterBar
          filter={filter}
          facets={facets}
          matchCount={matchCount}
          totalCount={totalCount}
          onChange={setFilter}
        >
          {labelOptions && (
            <LabelsMenu
              choices={labelChoices}
              rackOptions={labelOptions.rack}
              itemOptions={labelOptions.item}
              itemCount={labelOptions.itemCount}
              onChange={setLabelChoices}
            />
          )}
          <Button size="sm" variant="outline" onPress={() => setIsExportOpen(true)}>
            <DownloadIcon />
            Export
          </Button>
        </FilterBar>
      )}

      {!elevation || !mapping ? (
        <div className="p-8 text-center text-foreground-muted text-sm">
          {mapping ? `No objects of kind ${mapping.rackKind} exist.` : "Create a mapping to start."}
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          <div className="min-w-0 flex-1 overflow-auto p-6">
            {view === "2d" ? (
              <RackElevation2D elevation={elevation} {...interactions} />
            ) : (
              <RackElevation3D elevation={elevation} {...interactions} />
            )}
          </div>
          <aside className="flex w-80 shrink-0 flex-col gap-3 overflow-auto border-l p-3">
            {elevation.issues.length > 0 && (
              <Section title={`Issues (${elevation.issues.length})`}>
                <ul className="flex list-disc flex-col gap-1 pl-4 text-warning text-xs">
                  {elevation.issues.map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              </Section>
            )}
            <Section title={`Not mounted (${elevation.unplaced.length})`}>
              {elevation.unplaced.length === 0 ? (
                <p className="text-foreground-muted text-xs">
                  Every related object has a position.
                </p>
              ) : (
                <ul className="flex flex-col">
                  {elevation.unplaced.map((item) => (
                    <li key={item.key}>
                      <button
                        type="button"
                        onClick={() => openRootNode(item.node.id)}
                        className={classNames(
                          "flex w-full items-center gap-2 rounded-md px-1 py-1 text-left text-sm hover:bg-content-strong",
                          matchedKeys && !matchedKeys.has(item.key) && "opacity-30"
                        )}
                      >
                        <span
                          className="size-2.5 shrink-0 rounded-sm"
                          style={{ background: item.color }}
                        />
                        <span className="truncate">{item.label}</span>
                        <span className="ml-auto text-foreground-muted text-xs">
                          {item.sourceName} · {item.height}U
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-foreground-muted text-xs">
                Select an empty unit in the rack to mount one of these objects.
              </p>
            </Section>
            <Legend sources={mapping.itemSources.map((source) => source.name)} />
            <ChangesPanel onOpenNode={openRootNode} />
          </aside>
        </div>
      )}

      {elevation && mapping && (
        <ExportDialog
          isOpen={isExportOpen}
          onOpenChange={setIsExportOpen}
          elevation={elevation}
          mappingName={mapping.name}
          matchedKeys={matchedKeys}
        />
      )}

      <Sheet aria-label="Rack elevation details" isOpen={isSheetOpen} onOpenChange={setIsSheetOpen}>
        {sheet?.type === "node" && (
          <ObjectDetails
            key={sheet.stack.join("/")}
            nodeId={sheet.stack.at(-1) ?? ""}
            elevation={elevation}
            mapping={mapping ?? null}
            onOpenNode={openNode}
            onBack={
              sheet.stack.length > 1
                ? () => setSheet({ type: "node", stack: sheet.stack.slice(0, -1) })
                : undefined
            }
            onClose={() => setIsSheetOpen(false)}
          />
        )}
        {sheet?.type === "unit" && elevation && mapping && (
          <UnitDetails
            unit={sheet.unit}
            face={sheet.face}
            elevation={elevation}
            mapping={mapping}
            onOpenNode={openNode}
            onClose={() => setIsSheetOpen(false)}
          />
        )}
      </Sheet>
    </div>
  );
}

function Legend({ sources }: { sources: string[] }) {
  return (
    <Section title="How to use">
      <ul className="flex list-disc flex-col gap-1 pl-4 text-foreground-muted text-xs">
        <li>Select the rack name, a unit or an object to view its details.</li>
        <li>Drag an object to another unit, or to the other face, to move it.</li>
        <li>Hatched objects are full depth and mounted on the other face.</li>
        <li>This mapping reads {sources.join(", ").toLowerCase()} from the rack.</li>
      </ul>
    </Section>
  );
}
