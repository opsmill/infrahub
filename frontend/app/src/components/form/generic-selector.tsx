import { Combobox, tComboboxItem } from "@/components/ui/combobox-legacy";
import { useId } from "react";
import Label from "@/components/ui/label";
import { useAtomValue } from "jotai/index";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { PROFILE_KIND } from "@/config/constants";

type GenericSelectorProps = {
  currentKind: string;
  kindInheritingFromGeneric: string[];
  value?: string;
  onChange: (item: string) => void;
};

export const GenericSelector = ({
  currentKind,
  kindInheritingFromGeneric,
  ...props
}: GenericSelectorProps) => {
  const id = useId();
  const nodeSchemas = useAtomValue(schemaState);
  const nodeGenerics = useAtomValue(genericsState);
  const profileSchemas = useAtomValue(profilesAtom);

  const items: Array<tComboboxItem> = kindInheritingFromGeneric
    .map((usedByKind) => {
      const relatedSchema = [...nodeSchemas, ...profileSchemas].find(
        (schema) => schema.kind === usedByKind
      );

      if (!relatedSchema) return;

      // When choosing a profile, display informations about the related node
      if (currentKind === PROFILE_KIND) {
        const relationship = relatedSchema.relationships?.find(
          (relationship) => relationship.name === "related_nodes"
        );

        const nodeSchema =
          relationship?.peer &&
          [...nodeSchemas, ...nodeGenerics, ...profileSchemas].find(
            (schema) => schema.kind === relationship.peer
          );

        if (!nodeSchema) return;

        return {
          value: relatedSchema.kind,
          label: nodeSchema.label ?? nodeSchema.name,
          badge: nodeSchema.namespace,
        };
      }

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
