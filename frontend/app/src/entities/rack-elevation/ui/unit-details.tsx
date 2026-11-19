import { Button } from "@infrahub/ui";

import type { Elevation, RackFace } from "@/entities/rack-elevation/domain/model/elevation";
import type { RackElevationMapping } from "@/entities/rack-elevation/domain/model/mapping";
import { occupiesFace } from "@/entities/rack-elevation/domain/rules/build-elevation";
import {
  buildPlacementUpdates,
  checkPlacement,
} from "@/entities/rack-elevation/domain/rules/placement";
import { Section, SheetHeader } from "@/entities/rack-elevation/ui/object-details";
import { useRackElevationStore } from "@/entities/rack-elevation/ui/rack-elevation-store";

interface UnitDetailsProps {
  unit: number;
  face: RackFace;
  elevation: Elevation;
  mapping: RackElevationMapping;
  onOpenNode: (nodeId: string) => void;
  onClose: () => void;
}

export function UnitDetails({
  unit,
  face,
  elevation,
  mapping,
  onOpenNode,
  onClose,
}: UnitDetailsProps) {
  const { schema, updateAttributes } = useRackElevationStore();
  const occupants = elevation.placed.filter(
    (item) =>
      item.position !== null &&
      item.position <= unit &&
      unit < item.position + item.height &&
      occupiesFace(item, face)
  );
  const candidates = [
    ...elevation.unplaced,
    ...elevation.placed.filter((item) => !occupants.includes(item)),
  ];

  return (
    <div className="flex flex-col gap-4">
      <SheetHeader
        eyebrow={`${elevation.label} · ${face === "front" ? "Front" : "Rear"}`}
        title={`U${unit}`}
        onClose={onClose}
      />
      <Section title="Occupied by">
        {occupants.length === 0 ? (
          <p className="text-foreground-muted text-sm">This unit is empty on the {face} face.</p>
        ) : (
          occupants.map((item) => (
            <Button
              key={item.key}
              size="sm"
              variant="outline"
              onPress={() => onOpenNode(item.node.id)}
            >
              {item.label}
              {item.face !== face ? ` (mounted ${item.face}, full depth)` : ""}
            </Button>
          ))
        )}
      </Section>
      {occupants.length === 0 && (
        <Section title={`Mount at U${unit}`}>
          <p className="text-foreground-muted text-xs">
            Mounting writes the position and face to the object through the mapping.
          </p>
          <ul className="flex flex-col gap-1">
            {candidates.map((item) => {
              const placement = { position: unit, face };
              const check = checkPlacement(elevation, item, placement);
              return (
                <li key={item.key} className="flex items-center gap-2 text-sm">
                  <span
                    className="size-2.5 shrink-0 rounded-sm"
                    style={{ background: item.color }}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{item.label}</span>
                    <span className="block truncate text-foreground-muted text-xs">
                      {item.position === null
                        ? "Not mounted"
                        : `Now at U${item.position} ${item.face}`}
                      {` · ${item.height}U`}
                      {check.ok ? "" : ` · ${check.reason}`}
                    </span>
                  </span>
                  <Button
                    size="xs"
                    variant="outline"
                    isDisabled={!check.ok}
                    onPress={() =>
                      updateAttributes(buildPlacementUpdates(item, placement, mapping, schema))
                    }
                  >
                    {item.position === null ? "Mount" : "Move here"}
                  </Button>
                </li>
              );
            })}
          </ul>
        </Section>
      )}
    </div>
  );
}
