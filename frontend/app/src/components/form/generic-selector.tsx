import { Combobox, tComboboxItem } from "@/components/ui/combobox";
import { useId } from "react";
import Label from "@/components/ui/label";
import { useAtomValue } from "jotai/index";
import { profilesAtom, schemaState } from "@/state/atoms/schema.atom";

type GenericSelectorProps = {
  kindInheritingFromGeneric: string[];
  value?: string;
  onChange: (item: string) => void;
};

export const GenericSelector = ({ kindInheritingFromGeneric, ...props }: GenericSelectorProps) => {
  const id = useId();
  const nodeSchemas = useAtomValue(schemaState);
  const profileSchemas = useAtomValue(profilesAtom);

  const items: Array<tComboboxItem> = kindInheritingFromGeneric
    .map((kind) => {
      const relatedSchema = [...nodeSchemas, ...profileSchemas].find(
        (schema) => schema.kind === kind
      );

      if (!relatedSchema) return null;

      return {
        value: relatedSchema.kind,
        label: relatedSchema.label ?? relatedSchema.name,
        badge: relatedSchema.namespace,
      };
    })
    .filter((item) => !!item);

  return (
    <div className="p-4 bg-gray-200">
      <Label htmlFor={id}>Select an object type</Label>
      <Combobox id={id} items={items} {...props} />
    </div>
  );
};
