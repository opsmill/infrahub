import { Button } from "@/shared/components/aria/button";
import { Col } from "@/shared/components/container";
import { Badge } from "@/shared/components/ui/badge";

import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";

interface RelationshipFilterComboboxProps {
  peer: string;
  value: RelationshipNode[] | undefined;
  onChange: (value: RelationshipNode[]) => void;
}

export function RelationshipFilterCombobox({
  peer,
  value,
  onChange,
}: RelationshipFilterComboboxProps) {
  return (
    <div className="min-h-0 overflow-hidden rounded-md border border-gray-300 bg-white">
      {!!value?.length && (
        <Col className="max-h-24 items-start overflow-y-auto border-gray-300 border-b p-2">
          {value.map(({ id, display_label }) => (
            <Badge key={id} className="inline-flex items-center gap-1 pr-0.5">
              {display_label}

              <Button
                size="xs"
                shape="circle"
                variant="ghost"
                onPress={() => onChange(value.filter((item) => item.id !== id))}
                className="h-4 w-4 text-gray-500 data-hovered:text-gray-800"
                aria-label="Remove"
                data-testid="remove-option"
              >
                &times;
              </Button>
            </Badge>
          ))}
        </Col>
      )}

      <RelationshipComboboxList
        peer={peer}
        onSelect={(relationship) => {
          onChange(value ? [...value, relationship] : [relationship]);
        }}
        filterItem={(node) => !value?.some((v) => v.id === node.id)}
        autoFocus
      />
    </div>
  );
}
