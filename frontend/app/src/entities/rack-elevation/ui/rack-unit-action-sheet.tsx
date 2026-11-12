import { Button, Select, SelectItem, SelectList, SelectTrigger, Sheet } from "@infrahub/ui";
import { useAtomValue } from "jotai";
import { useState } from "react";

import { Col } from "@/shared/components/container";
import { SlideOverTitle } from "@/shared/components/display/slide-over";
import ObjectForm from "@/shared/components/form/object-form";

import type {
  RackElevationItem,
  RackFace,
} from "@/entities/rack-elevation/domain/model/rack-elevation";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface RackUnitActionTarget {
  unit: number;
  face: RackFace;
}

export interface RackUnitActionSheetProps {
  target: RackUnitActionTarget | null;
  rackName: string;
  unpositionedItems: RackElevationItem[];
  mountableKinds: string[];
  isPlacing: boolean;
  onClose: () => void;
  onPlaceItem: (itemId: string) => void;
}

export function RackUnitActionSheet({ target, onClose, ...props }: RackUnitActionSheetProps) {
  return (
    <Sheet
      isOpen={target !== null}
      onOpenChange={(isOpen) => {
        if (!isOpen) onClose();
      }}
      aria-label="Place an item in a free unit"
    >
      {target && <ActionSheetContent target={target} onClose={onClose} {...props} />}
    </Sheet>
  );
}

interface ActionSheetContentProps extends Omit<RackUnitActionSheetProps, "target"> {
  target: RackUnitActionTarget;
}

function ActionSheetContent({
  target,
  rackName,
  unpositionedItems,
  mountableKinds,
  isPlacing,
  onClose,
  onPlaceItem,
}: ActionSheetContentProps) {
  const [newItemKind, setNewItemKind] = useState<string | null>(null);
  const { schema: newItemSchema } = useSchema(newItemKind);
  const nodeSchemas = useAtomValue(nodeSchemasAtom);
  const kindOptions = nodeSchemas
    .filter((schema) => mountableKinds.includes(schema.kind))
    .map((schema) => ({ id: schema.kind, label: schema.label ?? schema.kind }));
  const where = `unit ${target.unit}, ${target.face.toLowerCase()} of ${rackName}`;

  if (newItemKind && newItemSchema) {
    return (
      <>
        <SlideOverTitle
          schema={newItemSchema}
          currentObjectLabel="New"
          title={`Create ${newItemSchema.label} in ${where}`}
          subtitle={newItemSchema.description}
        />
        <ObjectForm
          kind={newItemKind}
          onSuccess={(newObject) => onPlaceItem(newObject.id)}
          onCancel={() => setNewItemKind(null)}
        />
      </>
    );
  }

  return (
    <Col className="gap-6" data-testid="rack-unit-action-sheet">
      <h2 className="font-semibold text-lg">Place an item at {where}</h2>

      <Col>
        <h3 className="font-semibold text-sm">Place an item that has no unit</h3>
        {unpositionedItems.length === 0 && (
          <p className="text-foreground-muted text-sm">No item in this rack is without a unit.</p>
        )}
        {unpositionedItems.map((item) => (
          <Button
            key={item.id}
            variant="outline"
            size="sm"
            className="justify-start"
            isDisabled={isPlacing}
            data-testid={`rack-place-${item.display_label}`}
            onPress={() => onPlaceItem(item.id)}
          >
            {item.label} ({item.u_height}U)
          </Button>
        ))}
      </Col>

      <Col>
        <h3 className="font-semibold text-sm">Create a new item</h3>
        <Select
          aria-label="Kind of the new item"
          placeholder="Select a kind"
          value={newItemKind}
          onChange={(key) => setNewItemKind(key === null ? null : String(key))}
        >
          <SelectTrigger size="sm" />
          <SelectList items={kindOptions} width="trigger">
            {(option) => <SelectItem>{option.label}</SelectItem>}
          </SelectList>
        </Select>
      </Col>

      <Button variant="outline" size="sm" onPress={onClose}>
        Cancel
      </Button>
    </Col>
  );
}
