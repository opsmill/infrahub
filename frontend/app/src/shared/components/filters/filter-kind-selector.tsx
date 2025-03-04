import { nodeSchemasAtom, profileSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { GenericSchema } from "@/entities/schema/types";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import useFilters from "@/shared/hooks/useFilters";
import { useAtomValue } from "jotai/index";
import { useState } from "react";

export const FilterKindSelector = ({
  genericSchema,
  showLabel = true,
}: { genericSchema: GenericSchema; showLabel?: boolean }) => {
  const [activeFilters] = useFilters();
  const availableNodes = useAtomValue(nodeSchemasAtom);
  const availableProfiles = useAtomValue(profileSchemasAtom);
  const allAvailableSchemas = [...availableNodes, ...availableProfiles];

  const selectedKindFilter = activeFilters.find((filter) => filter.name === "kind__value");
  const compatibleSchemas = (genericSchema.used_by ?? [])
    .map((kindValue) => {
      if (!allAvailableSchemas) return null;

      return allAvailableSchemas.find((schema) => schema.kind === kindValue);
    })
    .filter((schema) => !!schema);

  return (
    <FormField
      name="kind"
      defaultValue={
        selectedKindFilter
          ? { source: { type: "user" }, value: selectedKindFilter.value }
          : DEFAULT_FORM_FIELD_VALUE
      }
      render={({ field }) => {
        const [isDropdownOpen, setIsDropdownOpen] = useState(false);
        const currentFieldValue = field.value;
        const selectedSchema = allAvailableSchemas.find(
          (schema) => schema.kind === currentFieldValue?.value
        );

        return (
          <div className="flex flex-col gap-2">
            {showLabel && <LabelFormField label="Kind" fieldData={currentFieldValue} />}

            <Combobox open={isDropdownOpen} onOpenChange={setIsDropdownOpen}>
              <FormInput>
                <ComboboxTrigger aria-label="kind">
                  {selectedSchema && (
                    <div className="w-full flex justify-between">
                      {selectedSchema.label} <Badge>{selectedSchema.namespace}</Badge>
                    </div>
                  )}
                </ComboboxTrigger>
              </FormInput>

              <ComboboxContent>
                <ComboboxList>
                  {compatibleSchemas.map((schemaOption) => (
                    <ComboboxItem
                      key={schemaOption.kind}
                      selectedValue={selectedSchema?.kind}
                      value={schemaOption.kind!}
                      onSelect={() => {
                        const newSelectedValue =
                          schemaOption.kind === selectedSchema?.kind ? null : schemaOption.kind;
                        field.onChange(
                          updateFormFieldValue(newSelectedValue ?? null, DEFAULT_FORM_FIELD_VALUE)
                        );
                        setIsDropdownOpen(false);
                      }}
                    >
                      {schemaOption.label}{" "}
                      <Badge className="ml-auto">{schemaOption?.namespace}</Badge>
                    </ComboboxItem>
                  ))}
                </ComboboxList>
              </ComboboxContent>
            </Combobox>

            <FormMessage />
          </div>
        );
      }}
    />
  );
};
