import { useAtomValue } from "jotai";
import { forwardRef } from "react";

import { ComboboxEmpty, ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";

import { nodeSchemasAtom, profileSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { ModelSchema } from "@/entities/schema/types";

export interface SchemaComboboxListProps {
  onSelect: (value: ModelSchema) => void;
  value?: string | null;
}

export const SchemaComboboxList = forwardRef<HTMLDivElement, SchemaComboboxListProps>(
  ({ value, onSelect }, ref) => {
    const nodeSchemas = useAtomValue(nodeSchemasAtom);
    const profileSchemas = useAtomValue(profileSchemasAtom);

    const schemaList: Array<ModelSchema> = [...nodeSchemas, ...profileSchemas];

    return (
      <ComboboxList ref={ref}>
        <ComboboxEmpty>No kind found</ComboboxEmpty>

        {schemaList.map((schema) => {
          return (
            <ComboboxItem
              key={schema.kind}
              value={schema.kind}
              selectedValue={value}
              onSelect={() => onSelect(schema)}
            >
              <span className="truncate">{schema.label}</span>
            </ComboboxItem>
          );
        })}
      </ComboboxList>
    );
  }
);
