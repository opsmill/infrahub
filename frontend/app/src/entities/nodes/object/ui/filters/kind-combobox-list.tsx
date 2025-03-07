import { nodeSchemasAtom, profileSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import { ComboboxEmpty, ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";
import { useAtomValue } from "jotai";
import { forwardRef } from "react";

export interface KindComboboxListProps {
  onSelect: (value: string) => void;
  value?: string | null;
}

export const KindComboboxList = forwardRef<HTMLDivElement, KindComboboxListProps>(
  ({ value, onSelect }, ref) => {
    const nodeSchemas = useAtomValue(nodeSchemasAtom);
    const profileSchemas = useAtomValue(profileSchemasAtom);
    const schemaKindLabel = useAtomValue(schemaKindLabelState);

    const kindList: Array<string> = [
      ...nodeSchemas.map((schema) => {
        return schema.kind;
      }),
      ...profileSchemas.map((schema) => {
        return schema.kind;
      }),
    ];

    return (
      <ComboboxList ref={ref}>
        <ComboboxEmpty>No kind found</ComboboxEmpty>

        {kindList.map((kind) => {
          return (
            <ComboboxItem
              key={kind}
              value={kind}
              selectedValue={value}
              onSelect={() => onSelect(kind)}
            >
              <span className="truncate">{schemaKindLabel[kind]}</span>
            </ComboboxItem>
          );
        })}
      </ComboboxList>
    );
  }
);
