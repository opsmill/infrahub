import { useAtomValue } from "jotai";
import type * as React from "react";

import { Badge } from "@/shared/components/ui/badge";
import { ComboboxEmpty, ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { ModelSchema } from "@/entities/schema/types";

export interface TargetSchemaComboboxListProps {
  onSelect: (value: ModelSchema) => void;
  value?: string | null;
  ref?: React.Ref<HTMLDivElement>;
}

export function TargetSchemaComboboxList({ value, onSelect, ref }: TargetSchemaComboboxListProps) {
  const nodeSchemas = useAtomValue(nodeSchemasAtom);

  return (
    <ComboboxList ref={ref} shouldFilter>
      <ComboboxEmpty>No target schema found</ComboboxEmpty>

      {nodeSchemas.map((schema) => {
        return (
          <ComboboxItem
            key={schema.id}
            value={schema.label!}
            keywords={[schema.label!, schema.kind!]}
            selectedValue={value}
            onSelect={() => onSelect(schema)}
          >
            <span className="truncate">{schema.label}</span>
            <Badge className="ml-auto font-medium">{schema.namespace}</Badge>
          </ComboboxItem>
        );
      })}
    </ComboboxList>
  );
}
